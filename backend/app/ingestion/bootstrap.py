from __future__ import annotations

from app.ingestion.service import MailIngestionService
from app.ingestion.sqlite_repositories import (
    SQLiteCheckpointRepository,
    SQLiteConnectionFactory,
    SQLiteMessageMetadataRepository,
)
from app.providers.factory import ProviderRegistry


def build_ingestion_service(registry: ProviderRegistry, db_path: str) -> MailIngestionService:
    connections = SQLiteConnectionFactory(db_path)
    checkpoints = SQLiteCheckpointRepository(connections)
    metadata = SQLiteMessageMetadataRepository(connections)
    return MailIngestionService(
        registry=registry,
        checkpoint_repository=checkpoints,
        metadata_repository=metadata,
    )
