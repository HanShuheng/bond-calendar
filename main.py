from __future__ import annotations

import html
import json
import re
import sys
import time
import warnings
from datetime import date, datetime, time as clock_time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from ics import Calendar, DisplayAlarm, Event


CALENDAR_URL = "https://www.jisilu.cn/data/calendar/get_calendar_data/?qtype=CNV"
JISILU_BASE_URL = "https://www.jisilu.cn"
OUTPUT_FILE = Path("kzz.ics")
TIMEZONE = ZoneInfo("Asia/Shanghai")

EVENT_KEYWORDS = [
    "申购日",
    "上市日",
]

EVENT_UID_TYPES = {
    "申购日": "subscribe",
    "上市日": "list",
}

EVENT_START_TIME = clock_time(9, 30)
EVENT_DURATION = timedelta(minutes=5)
ALARM_RULES = {
    "申购日": (
        timedelta(minutes=30),  # 10:00
        timedelta(hours=3),  # 12:30
    ),
    "上市日": (
        timedelta(days=-1),
        timedelta(minutes=-30),  # 09:00
    ),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.jisilu.cn/data/calendar/",
}


def fetch_calendar_data(retries: int = 3, timeout: int = 15) -> list[dict[str, Any]] | None:
    """Fetch convertible bond calendar data. Return None on upstream failure."""
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(CALENDAR_URL, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError(f"Expected JSON list, got {type(data).__name__}")
            events: list[dict[str, Any]] = []
            for index, item in enumerate(data, start=1):
                if isinstance(item, dict):
                    events.append(item)
                else:
                    print(f"Warning: skip item #{index}, expected object: {item!r}", file=sys.stderr)
            return events
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            print(f"Warning: fetch attempt {attempt}/{retries} failed: {exc}", file=sys.stderr)
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))

    print(f"Warning: upstream calendar fetch failed, keep existing {OUTPUT_FILE}: {last_error}", file=sys.stderr)
    return None


def matched_keyword(title: str) -> str | None:
    for keyword in EVENT_KEYWORDS:
        if keyword in title:
            return keyword
    return None


def parse_event_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def clean_description(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def filter_bond_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []

    for index, item in enumerate(raw_events, start=1):
        title = item.get("title")
        code = item.get("code")
        start = item.get("start")

        if not title or not code or not start:
            print(f"Warning: skip item #{index}, missing title/start/code: {item!r}", file=sys.stderr)
            continue
        if not isinstance(title, str) or not isinstance(code, str):
            print(f"Warning: skip item #{index}, invalid title/code type: {item!r}", file=sys.stderr)
            continue

        keyword = matched_keyword(title)
        if keyword is None:
            continue

        event_date = parse_event_date(start)
        if event_date is None:
            print(f"Warning: skip {title}, invalid date: {start!r}", file=sys.stderr)
            continue

        filtered.append(
            {
                "id": item.get("id"),
                "title": title.strip(),
                "code": code.strip(),
                "date": event_date,
                "keyword": keyword,
                "description": clean_description(item.get("description")),
                "url": item.get("url"),
            }
        )

    return filtered


def event_time_range(event_date: date, keyword: str) -> tuple[datetime, datetime]:
    begin = datetime.combine(event_date, EVENT_START_TIME, tzinfo=TIMEZONE)
    end = begin + EVENT_DURATION
    return begin, end


def detail_url_for(code: str, raw_url: Any) -> str:
    if isinstance(raw_url, str) and raw_url.startswith("http"):
        return raw_url
    if isinstance(raw_url, str) and raw_url.startswith("/"):
        return f"{JISILU_BASE_URL}{raw_url}"
    return f"{JISILU_BASE_URL}/data/convert_bond_detail/{code}"


def build_event(item: dict[str, Any]) -> Event:
    begin, end = event_time_range(item["date"], item["keyword"])
    detail_url = detail_url_for(item["code"], item.get("url"))

    event = Event()
    event.name = item["title"]
    event.begin = begin
    event.end = end
    uid_type = EVENT_UID_TYPES.get(item["keyword"], item["keyword"])
    event.uid = f"{item['code']}-{uid_type}-{item['date'].isoformat()}@bond-calendar"
    event.url = detail_url
    event.description = "\n".join(
        part
        for part in [
            item["title"],
            f"转债代码: {item['code']}",
            f"集思录详情页: {detail_url}",
            item.get("description", ""),
        ]
        if part
    )

    for trigger in ALARM_RULES.get(item["keyword"], ()):
        event.alarms.append(DisplayAlarm(trigger=trigger, display_text=item["title"]))

    return event


def sorted_events(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda event: (event["date"], event["code"], event["title"]))


def build_calendar(items: list[dict[str, Any]]) -> Calendar:
    calendar = Calendar()
    calendar.creator = "bond-calendar"

    for item in sorted_events(items):
        calendar.events.add(build_event(item))

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


def write_calendar(calendar: Calendar, output_file: Path = OUTPUT_FILE) -> None:
    tmp_file = output_file.with_suffix(output_file.suffix + ".tmp")
    tmp_file.write_text(stable_calendar_text(calendar), encoding="utf-8")
    tmp_file.replace(output_file)


def print_event_summary(items: list[dict[str, Any]]) -> None:
    if not items:
        return

    print("Matched bond events:")
    for item in sorted_events(items):
        print(f"- {item['date'].isoformat()} {item['code']} {item['title']}")


def main() -> int:
    raw_events = fetch_calendar_data()
    if raw_events is None:
        return 0

    matched_events = filter_bond_events(raw_events)
    if not matched_events:
        print("No matched bond events found.")

    calendar = build_calendar(matched_events)
    write_calendar(calendar)
    print(f"Fetched {len(raw_events)} raw events, wrote {len(matched_events)} matched events to {OUTPUT_FILE}.")
    print_event_summary(matched_events)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
