from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class StageOutputRecord:
    account_email: str
    message_identity: str
    stage_name: str
    output_json: dict[str, object]
    model_provider: str
    model_name: str
    model_version: str
    attempts: int
    used_fallback: bool
    failure_reason: str | None
    processed_at: datetime


class AIResultRepository(Protocol):
    def upsert_stage_output(self, record: StageOutputRecord) -> None:
        ...
