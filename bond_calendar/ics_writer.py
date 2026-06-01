from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path

from ics import Calendar, DisplayAlarm, Event

from .models import BondEvent, CalendarConfig


def event_title(item: BondEvent, config: CalendarConfig) -> str:
    rule = config.event_rules[item.event_type]
    return f"【{rule.label}】{item.name}"


def build_event(item: BondEvent, config: CalendarConfig) -> Event:
    rule = config.event_rules[item.event_type]
    begin = datetime.combine(item.event_date, config.event_start_time, tzinfo=config.timezone)
    end = begin + config.event_duration
    detail_url = item.detail_url or ""
    title = event_title(item, config)

    event = Event()
    event.name = title
    event.begin = begin
    event.end = end
    event.uid = f"{item.code}-{rule.uid_type}-{item.event_date.isoformat()}@bond-calendar"
    if detail_url:
        event.url = detail_url
    event.description = "\n".join(
        part
        for part in [
            title,
            f"代码: {item.code}",
            *item.description_fields,
            f"详情: {detail_url}" if detail_url else None,
        ]
        if part
    )

    for trigger in rule.alarms:
        event.alarms.append(DisplayAlarm(trigger=trigger, display_text=title))

    return event


def sorted_events(items: list[BondEvent], config: CalendarConfig) -> list[BondEvent]:
    return sorted(items, key=lambda event: (event.event_date, event.code, event_title(event, config)))


def build_calendar(items: list[BondEvent], config: CalendarConfig) -> Calendar:
    calendar = Calendar()
    calendar.creator = config.creator

    for item in sorted_events(items, config):
        calendar.events.add(build_event(item, config))

    return calendar


def stable_calendar_text(calendar: Calendar) -> str:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning, module=r"ics\.component")
        serialized = calendar.serialize()
    return sort_event_blocks(serialized)


def sort_event_blocks(serialized: str) -> str:
    prefix: list[str] = []
    suffix: list[str] = []
    blocks: list[list[str]] = []
    current_block: list[str] | None = None
    seen_event = False

    for line in serialized.splitlines(keepends=True):
        marker = line.strip()
        if marker == "BEGIN:VEVENT":
            current_block = [line]
            seen_event = True
            continue
        if current_block is not None:
            current_block.append(line)
            if marker == "END:VEVENT":
                blocks.append(current_block)
                current_block = None
            continue
        if seen_event:
            suffix.append(line)
        else:
            prefix.append(line)

    sorted_event_lines = [line for block in sorted(blocks, key=event_block_sort_key) for line in block]
    return "".join(prefix + sorted_event_lines + suffix)


def event_block_sort_key(block: list[str]) -> tuple[str, str, str]:
    fields: dict[str, str] = {}
    for line in block:
        if ":" not in line:
            continue
        key, value = line.strip().split(":", 1)
        if key in {"DTSTART", "SUMMARY", "UID"}:
            fields[key] = value
    return (fields.get("DTSTART", ""), fields.get("SUMMARY", ""), fields.get("UID", ""))


def write_calendar(calendar: Calendar, output_file: Path) -> None:
    tmp_file = output_file.with_suffix(output_file.suffix + ".tmp")
    tmp_file.write_text(stable_calendar_text(calendar), encoding="utf-8")
    tmp_file.replace(output_file)

