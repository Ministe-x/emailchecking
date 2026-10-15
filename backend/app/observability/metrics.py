from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol


class MetricsSink(Protocol):
    def increment(self, metric_name: str, value: int = 1, **tags: str) -> None:
        ...

    def event(self, name: str, **fields: object) -> None:
        ...


@dataclass
class LoggingMetricsSink:
    """Writes metrics as log records; the values travel in `extra` for a JSON formatter."""

    logger: logging.Logger

    def increment(self, metric_name: str, value: int = 1, **tags: str) -> None:
        self.logger.info(
            "metric.increment", extra={"metric": metric_name, "value": value, "tags": tags}
        )

    def event(self, name: str, **fields: object) -> None:
        self.logger.info("metric.event", extra={"event": name, "fields": fields})


class InMemoryMetricsSink:
    """Keeps counters in memory so tests can assert on them."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.events: list[dict[str, Any]] = []

    def increment(self, metric_name: str, value: int = 1, **tags: str) -> None:
        key = _metric_key(metric_name, tags)
        self.counts[key] += value

    def event(self, name: str, **fields: object) -> None:
        self.events.append({"name": name, "fields": dict(fields)})


def _metric_key(metric_name: str, tags: dict[str, str]) -> str:
    if not tags:
        return metric_name
    tag_text = ",".join(f"{k}={tags[k]}" for k in sorted(tags))
    return f"{metric_name}|{tag_text}"
