from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


EVENT_LABELS = {
    "subscribe": "申购日",
    "ballot": "中签公布",
    "list": "上市日",
}


@dataclass(frozen=True)
class EventRule:
    label: str
    uid_type: str
    alarms: tuple[timedelta, ...]


@dataclass(frozen=True)
class CalendarConfig:
    output_file: Path
    timezone: ZoneInfo
    event_lookback_days: int
    event_start_time: time
    event_duration: timedelta
    creator: str
    sources: tuple[str, ...]
    event_rules: dict[str, EventRule]
    adapters: dict[str, dict[str, object]]


@dataclass(frozen=True)
class BondEvent:
    code: str
    name: str
    event_type: str
    event_date: date
    detail_url: str | None = None
    description_fields: tuple[str, ...] = field(default_factory=tuple)
    source: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("BondEvent.code is required")
        if not self.name.strip():
            raise ValueError("BondEvent.name is required")
        if self.event_type not in EVENT_LABELS:
            raise ValueError(f"Unsupported event_type: {self.event_type!r}")


@dataclass(frozen=True)
class AdapterResult:
    source: str
    raw_count: int
    events: tuple[BondEvent, ...]

