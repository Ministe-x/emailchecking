from __future__ import annotations

from app.ai.client import DeterministicStubAIModelClient, ModelDescriptor
from app.ai.pipeline import AIPipelineService, RetryPolicy, StageRunner
from app.ai.sqlite_repositories import SQLiteAIResultRepository
from app.config import AIModelConfig
from app.ingestion.sqlite_repositories import SQLiteConnectionFactory


def build_ai_pipeline_service(*, db_path: str, config: AIModelConfig) -> AIPipelineService:
    connections = SQLiteConnectionFactory(db_path)
    repository = SQLiteAIResultRepository(connections)
    client = _build_client(config)
    runner = StageRunner(
        client=client,
        model=ModelDescriptor(
            provider=config.provider,
            name=config.model_name,
            version=config.model_version,
        ),
        retry_policy=RetryPolicy(max_attempts=config.max_retries),
    )
    return AIPipelineService(stage_runner=runner, repository=repository)


def _build_client(config: AIModelConfig) -> DeterministicStubAIModelClient:
    if config.provider != "stub":
        raise ValueError(
            f"Unsupported AI_MODEL_PROVIDER {config.provider!r}; only 'stub' is implemented"
        )
    return DeterministicStubAIModelClient()
