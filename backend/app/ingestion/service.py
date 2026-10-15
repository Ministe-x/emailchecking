from __future__ import annotations

import logging

from app.ingestion.dedup import deduplicate_messages
from app.ingestion.models import IngestionRunResult, NormalizedMailMessage
from app.ingestion.normalizer import normalize_envelope
from app.ingestion.repositories import CheckpointRepository, MessageMetadataRepository
from app.ingestion.threading import merge_trip_threads
from app.observability.metrics import MetricsSink
from app.providers.factory import ProviderRegistry
from app.providers.types import OAuthTokenSet, ProviderKind


class MailIngestionService:
    def __init__(
        self,
        registry: ProviderRegistry,
        checkpoint_repository: CheckpointRepository,
        metadata_repository: MessageMetadataRepository,
        metrics: MetricsSink | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._registry = registry
        self._checkpoints = checkpoint_repository
        self._metadata = metadata_repository
        self._metrics = metrics
        self._logger = logger or logging.getLogger(__name__)

    def run_incremental_sync(
        self,
        *,
        provider: ProviderKind,
        account_email: str,
        token_set: OAuthTokenSet,
        max_pages: int = 5,
    ) -> IngestionRunResult:
        account_email = account_email.strip().lower()
        self._emit_event(
            "sync.start",
            provider=provider.value,
            account_email=account_email,
            max_pages=max_pages,
        )
        provider_impl = self._registry.get(provider)
        checkpoint = self._checkpoints.get(provider, account_email)
        fetched_envelopes = []
        page_token: str | None = None

        for _ in range(max_pages):
            page = provider_impl.incremental_sync(
                token_set=token_set,
                checkpoint=checkpoint,
                page_token=page_token,
            )
            fetched_envelopes.extend(page.messages)
            checkpoint = page.next_checkpoint
            if not page.has_more:
                break
            page_token = page.next_page_token
            if page_token is None:
                break

        normalized = tuple(
            normalize_envelope(provider=provider, envelope=envelope)
            for envelope in fetched_envelopes
        )
        candidates = self._drop_existing_records(account_email, normalized)
        dedup_result = deduplicate_messages(candidates)
        stored_count = self._metadata.store_batch(account_email, dedup_result.unique_messages)
        trip_threads = merge_trip_threads(dedup_result.unique_messages)
        self._checkpoints.save(provider, account_email, checkpoint)

        result = IngestionRunResult(
            provider=provider,
            account_email=account_email,
            checkpoint=checkpoint,
            fetched_count=len(fetched_envelopes),
            normalized_count=len(normalized),
            stored_count=stored_count,
            deduped_count=dedup_result.dropped_count,
            trip_thread_count=len(trip_threads),
            messages=dedup_result.unique_messages,
            trip_threads=trip_threads,
        )
        self._increment("sync.fetched_messages", result.fetched_count, provider=provider.value)
        self._increment("sync.stored_messages", result.stored_count, provider=provider.value)
        self._increment("sync.deduped_messages", result.deduped_count, provider=provider.value)
        self._emit_event(
            "sync.finish",
            provider=provider.value,
            account_email=account_email,
            fetched_count=result.fetched_count,
            stored_count=result.stored_count,
            deduped_count=result.deduped_count,
            trip_thread_count=result.trip_thread_count,
        )
        return result

    def _drop_existing_records(
        self, account_email: str, messages: tuple[NormalizedMailMessage, ...]
    ) -> tuple[NormalizedMailMessage, ...]:
        new_messages: list[NormalizedMailMessage] = []
        for message in messages:
            if self._metadata.has_provider_message(
                message.provider, account_email, message.message_id
            ):
                continue
            if message.dedup_key and self._metadata.has_dedup_key(account_email, message.dedup_key):
                continue
            new_messages.append(message)
        return tuple(new_messages)

    def _increment(self, metric_name: str, value: int, **tags: str) -> None:
        if self._metrics is None or value <= 0:
            return
        self._metrics.increment(metric_name, value=value, **tags)

    def _emit_event(self, name: str, **fields: object) -> None:
        self._logger.info(
            "%s provider=%s account=%s",
            name,
            fields.get("provider"),
            fields.get("account_email"),
        )
        if self._metrics is None:
            return
        self._metrics.event(name, **fields)
