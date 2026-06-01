from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any

import requests

from ..models import AdapterResult, BondEvent, CalendarConfig
from ..utils import parse_event_date


JISILU_EVENT_TYPES = {
    "申购日": "subscribe",
    "中签公布": "ballot",
    "上市日": "list",
}


class JisiluAdapter:
    name = "集思录"

    def fetch(self, config: CalendarConfig, today: date | None = None) -> AdapterResult | None:
        settings = config.adapters.get("jisilu", {})
        rows = fetch_jisilu_calendar_data(settings)
        if rows is None:
            return None
        return AdapterResult(source=self.name, raw_count=len(rows), events=tuple(build_jisilu_events(rows, config, today=today)))


def fetch_jisilu_calendar_data(settings: dict[str, object]) -> list[dict[str, Any]] | None:
    url = str(settings["calendar_url"])
    base_url = str(settings["base_url"])
    retries = int(settings.get("retries", 3))
    timeout = int(settings.get("timeout", 15))
    headers = {
        "User-Agent": str(settings["user_agent"]),
        "Accept": "application/json,text/plain,*/*",
        "Referer": f"{base_url}/data/calendar/",
    }
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError(f"Expected JSON list, got {type(data).__name__}")
            return [item for item in data if isinstance(item, dict)]
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            print(f"Warning: Jisilu fetch attempt {attempt}/{retries} failed: {exc}", file=sys.stderr)
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))

    print(f"Warning: upstream calendar fetch failed: {last_error}", file=sys.stderr)
    return None


def build_jisilu_events(
    raw_events: list[dict[str, Any]],
    config: CalendarConfig,
    today: date | None = None,
) -> list[BondEvent]:
    base_url = str(config.adapters["jisilu"]["base_url"])
    current_date = today or datetime.now(config.timezone).date()
    cutoff = current_date - timedelta(days=config.event_lookback_days)
    events: list[BondEvent] = []

    for index, item in enumerate(raw_events, start=1):
        title = item.get("title")
        code = item.get("code")
        start = item.get("start")
        if not isinstance(title, str) or not isinstance(code, str) or not start:
            print(f"Warning: skip Jisilu item #{index}, missing title/start/code: {item!r}", file=sys.stderr)
            continue

        event_type = matched_event_type(title)
        event_date = parse_event_date(start)
        if event_type is None or event_date is None:
            continue
        if event_date < cutoff:
            continue

        events.append(
            BondEvent(
                code=code.strip(),
                name=clean_bond_name(title),
                event_type=event_type,
                event_date=event_date,
                detail_url=detail_url_for(base_url, code.strip(), item.get("url")),
                description_fields=tuple(clean_description(item.get("description")).splitlines()),
                source="集思录",
            )
        )

    return events


def matched_event_type(title: str) -> str | None:
    for keyword, event_type in JISILU_EVENT_TYPES.items():
        if keyword in title:
            return event_type
    return None


def clean_bond_name(title: str) -> str:
    return re.sub(r"^【[^】]+】", "", title).strip()


def clean_description(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def detail_url_for(base_url: str, code: str, raw_url: Any) -> str:
    if isinstance(raw_url, str) and raw_url.startswith("http"):
        return raw_url
    if isinstance(raw_url, str) and raw_url.startswith("/"):
        return f"{base_url}{raw_url}"
    return f"{base_url}/data/convert_bond_detail/{code}"
