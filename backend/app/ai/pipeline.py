from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from app.ai.client import (
    STAGE_AD_FILTER,
    STAGE_IMPORTANCE,
    STAGE_TRIP_RELEVANCE,
    AIModelClient,
    ModelDescriptor,
    ModelUnavailableError,
)
from app.ai.identity import build_message_identity
from app.ai.models import CalendarSeed, MessageAIResult, StageExecution
from app.ai.repositories import AIResultRepository, StageOutputRecord
from app.ai.rules import rule_based_ad_filter, rule_based_importance, rule_based_trip_relevance
from app.ai.schema import (
    SchemaValidationError,
    validate_ad_filter,
    validate_importance,
    validate_trip_relevance,
)
from app.ingestion.models import NormalizedMailMessage
from app.observability.metrics import MetricsSink


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("RetryPolicy.max_attempts must be >= 1")


class StageRunner:
    def __init__(
        self,
        client: AIModelClient,
        model: ModelDescriptor,
        retry_policy: RetryPolicy,
        metrics: MetricsSink | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._retry_policy = retry_policy
        self._metrics = metrics
        self._logger = logger or logging.getLogger(__name__)

    def run_ad_filter(self, message: NormalizedMailMessage) -> StageExecution:
        return self._run_stage(
            stage_name=STAGE_AD_FILTER,
            message=message,
            context={},
            validator=lambda payload: validate_ad_filter(payload).to_json(),
            fallback=lambda _: rule_based_ad_filter(message).to_json(),
        )

    def run_trip_relevance(
        self, message: NormalizedMailMessage, *, ad_filter_output: dict[str, object]
    ) -> StageExecution:
        return self._run_stage(
            stage_name=STAGE_TRIP_RELEVANCE,
            message=message,
            context={STAGE_AD_FILTER: ad_filter_output},
            validator=lambda payload: validate_trip_relevance(payload).to_json(),
            fallback=lambda _: rule_based_trip_relevance(message).to_json(),
        )

    def run_importance(
        self,
        message: NormalizedMailMessage,
        *,
        ad_filter_output: dict[str, object],
        trip_relevance_output: dict[str, object],
    ) -> StageExecution:
        return self._run_stage(
            stage_name=STAGE_IMPORTANCE,
            message=message,
            context={
                STAGE_AD_FILTER: ad_filter_output,
                STAGE_TRIP_RELEVANCE: trip_relevance_output,
            },
            validator=lambda payload: validate_importance(payload).to_json(),
            fallback=lambda _: rule_based_importance(
                message,
                ad_filter=validate_ad_filter(ad_filter_output),
                trip_relevance=validate_trip_relevance(trip_relevance_output),
            ).to_json(),
        )

    def _run_stage(
        self,
        *,
        stage_name: str,
        message: NormalizedMailMessage,
        context: dict[str, object],
        validator: Callable[[object], dict[str, object]],
        fallback: Callable[[dict[str, object]], dict[str, object]],
    ) -> StageExecution:
        last_failure: str | None = None
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            try:
                payload = self._client.run_stage(
                    stage_name=stage_name, message=message, context=context
                )
                validated = validator(payload)
                self._increment("ai.stage.success", stage=stage_name, fallback="false")
                return StageExecution(
                    stage_name=stage_name,
                    output_json=validated,
                    attempts=attempt,
                    used_fallback=False,
                    failure_reason=None,
                )
            except (SchemaValidationError, ModelUnavailableError, ValueError) as exc:
                last_failure = str(exc)
                self._increment("ai.stage.failure", stage=stage_name, fallback="false")
                self._logger.warning(
                    "ai.stage_attempt_failed stage=%s attempt=%s message_id=%s reason=%s",
                    stage_name,
                    attempt,
                    message.message_id,
                    last_failure,
                )

        fallback_payload = validator(fallback(context))
        self._increment("ai.stage.fallback", stage=stage_name, fallback="true")
        return StageExecution(
            stage_name=stage_name,
            output_json=fallback_payload,
            attempts=self._retry_policy.max_attempts,
            used_fallback=True,
            failure_reason=last_failure,
        )

    @property
    def model(self) -> ModelDescriptor:
        return self._model

    def _increment(self, metric_name: str, **tags: str) -> None:
        if self._metrics is None:
            return
        self._metrics.increment(metric_name, value=1, **tags)


class AIPipelineService:
    def __init__(
        self,
        stage_runner: StageRunner,
        repository: AIResultRepository,
        metrics: MetricsSink | None = None,
    ) -> None:
        self._runner = stage_runner
        self._repository = repository
        self._metrics = metrics

    def process_messages(
        self, *, account_email: str, messages: tuple[NormalizedMailMessage, ...]
    ) -> tuple[MessageAIResult, ...]:
        normalized_email = account_email.strip().lower()
        if self._metrics is not None:
            self._metrics.event(
                "ai.pipeline.start",
                account_email=normalized_email,
                message_count=len(messages),
            )
        results = [
            self._process_single(account_email=normalized_email, message=message)
            for message in messages
        ]
        if self._metrics is not None:
            self._metrics.increment("ai.pipeline.messages", value=len(results))
            self._metrics.event(
                "ai.pipeline.finish",
                account_email=normalized_email,
                processed_count=len(results),
            )
        return tuple(results)

    def _process_single(
        self, *, account_email: str, message: NormalizedMailMessage
    ) -> MessageAIResult:
        message_identity = build_message_identity(message)

        ad_exec = self._runner.run_ad_filter(message)
        trip_exec = self._runner.run_trip_relevance(message, ad_filter_output=ad_exec.output_json)
        importance_exec = self._runner.run_importance(
            message,
            ad_filter_output=ad_exec.output_json,
            trip_relevance_output=trip_exec.output_json,
        )
        for execution in (ad_exec, trip_exec, importance_exec):
            self._persist_stage(
                account_email=account_email,
                message_identity=message_identity,
                execution=execution,
            )

        ad_output = validate_ad_filter(ad_exec.output_json)
        trip_output = validate_trip_relevance(trip_exec.output_json)
        importance_output = validate_importance(importance_exec.output_json)
        calendar_seed = CalendarSeed(
            message_identity=message_identity,
            is_candidate=(trip_output.is_trip_related and not ad_output.is_ad),
            trip_type=trip_output.trip_type,
            priority_score=importance_output.priority_score,
        )
        return MessageAIResult(
            message=message,
            message_identity=message_identity,
            ad_filter=ad_output,
            trip_relevance=trip_output,
            importance=importance_output,
            calendar_seed=calendar_seed,
        )

    def _persist_stage(
        self,
        *,
        account_email: str,
        message_identity: str,
        execution: StageExecution,
    ) -> None:
        self._repository.upsert_stage_output(
            StageOutputRecord(
                account_email=account_email,
                message_identity=message_identity,
                stage_name=execution.stage_name,
                output_json=execution.output_json,
                model_provider=self._runner.model.provider,
                model_name=self._runner.model.name,
                model_version=self._runner.model.version,
                attempts=execution.attempts,
                used_fallback=execution.used_fallback,
                failure_reason=execution.failure_reason,
                processed_at=datetime.now(timezone.utc),
            )
        )
