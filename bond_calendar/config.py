from __future__ import annotations

import os
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

from .models import CalendarConfig, EventRule
from .utils import parse_duration


DEFAULT_CONFIG_FILE = Path("config/default.toml")


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(
    config_file: str | Path | None = None,
    output_file: str | Path | None = None,
    source: str | None = None,
) -> CalendarConfig:
    load_dotenv()

    config_path = Path(config_file or os.getenv("BOND_CALENDAR_CONFIG", DEFAULT_CONFIG_FILE))
    data = read_toml(config_path)

    calendar = data.get("calendar", {})
    if not isinstance(calendar, dict):
        raise ValueError("[calendar] must be a table")

    env_output = os.getenv("BOND_CALENDAR_OUTPUT")
    resolved_output = output_file or env_output or calendar.get("output_file", "kzz.ics")
    env_source = os.getenv("BOND_CALENDAR_SOURCE")
    resolved_sources = parse_sources(source or env_source or calendar.get("sources", ("eastmoney", "jisilu")))

    rules = parse_event_rules(data.get("events", {}))
    adapters = data.get("adapters", {})
    if not isinstance(adapters, dict):
        raise ValueError("[adapters] must be a table")

    return CalendarConfig(
        output_file=Path(resolved_output),
        timezone=ZoneInfo(str(calendar.get("timezone", "Asia/Shanghai"))),
        event_lookback_days=int(calendar.get("event_lookback_days", 7)),
        event_start_time=parse_time(str(calendar.get("event_start_time", "09:30"))),
        event_duration=timedelta(minutes=int(calendar.get("event_duration_minutes", 5))),
        creator=str(calendar.get("creator", "bond-calendar")),
        sources=resolved_sources,
        event_rules=rules,
        adapters={key: value for key, value in adapters.items() if isinstance(value, dict)},
    )


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        data = tomllib.load(file)
    if not isinstance(data, dict):
        raise ValueError("TOML root must be a table")
    return data


def parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def parse_sources(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        sources = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple)):
        sources = [str(part).strip() for part in value]
    else:
        raise ValueError("sources must be a comma-separated string or list")
    return tuple(source for source in sources if source)


def parse_event_rules(raw_events: Any) -> dict[str, EventRule]:
    if not isinstance(raw_events, dict):
        raise ValueError("[events] must be a table")

    rules: dict[str, EventRule] = {}
    for event_type, raw_rule in raw_events.items():
        if not isinstance(raw_rule, dict):
            raise ValueError(f"[events.{event_type}] must be a table")
        alarms = raw_rule.get("alarms", [])
        if not isinstance(alarms, list):
            raise ValueError(f"[events.{event_type}].alarms must be a list")
        rules[str(event_type)] = EventRule(
            label=str(raw_rule["label"]),
            uid_type=str(raw_rule["uid_type"]),
            alarms=tuple(parse_duration(str(value)) for value in alarms),
        )
    return rules
