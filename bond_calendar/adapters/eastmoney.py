from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any

import requests

from ..models import AdapterResult, BondEvent, CalendarConfig
from ..utils import (
    compact_join,
    format_event_date,
    format_percent,
    format_preplacing,
    format_scale,
    is_empty_value,
    optional_line,
    parse_event_date,
)


class EastmoneyAdapter:
    name = "东方财富"

    def fetch(self, config: CalendarConfig, today: date | None = None) -> AdapterResult | None:
        settings = config.adapters.get("eastmoney", {})
        rows = fetch_eastmoney_bond_data(settings)
        if rows is None:
            return None

        events = build_eastmoney_events(rows, config, today=today)
        return AdapterResult(source=self.name, raw_count=len(rows), events=tuple(events))


def fetch_eastmoney_bond_data(settings: dict[str, object]) -> list[dict[str, Any]] | None:
    api_url = str(settings["api_url"])
    page_url = str(settings["page_url"])
    page_size = int(settings.get("page_size", 500))
    retries = int(settings.get("retries", 3))
    timeout = int(settings.get("timeout", 15))
    params = dict(settings.get("params", {}))
    headers = {
        "User-Agent": str(settings["user_agent"]),
        "Accept": "application/json,text/plain,*/*",
        "Referer": page_url,
    }
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            rows: list[dict[str, Any]] = []
            page = 1
            total_pages = 1

            while page <= total_pages:
                request_params = {
                    **params,
                    "pageNumber": str(page),
                    "pageSize": str(page_size),
                }
                response = requests.get(api_url, headers=headers, params=request_params, timeout=timeout)
                response.raise_for_status()
                page_rows, total_pages = parse_eastmoney_payload(response.json(), page_size)
                rows.extend(page_rows)
                if not page_rows:
                    break
                page += 1

            return rows
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            print(f"Warning: Eastmoney fetch attempt {attempt}/{retries} failed: {exc}", file=sys.stderr)
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))

    print(f"Warning: Eastmoney fetch failed: {last_error}", file=sys.stderr)
    return None


def parse_eastmoney_payload(payload: Any, page_size: int) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(payload, dict):
        raise ValueError(f"Expected Eastmoney JSON object, got {type(payload).__name__}")
    if payload.get("success") is not True:
        raise ValueError(f"Eastmoney response success is not true: {payload.get('message')!r}")

    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("Eastmoney response missing result object")

    data = result.get("data")
    if not isinstance(data, list):
        raise ValueError("Eastmoney response missing result.data list")

    rows = [item for item in data if isinstance(item, dict)]
    pages = result.get("pages")
    if isinstance(pages, int) and pages > 0:
        return rows, pages

    count = result.get("count")
    if isinstance(count, int) and count > 0:
        return rows, max(1, (count + page_size - 1) // page_size)

    return rows, 1


def build_eastmoney_events(
    raw_rows: list[dict[str, Any]],
    config: CalendarConfig,
    today: date | None = None,
) -> list[BondEvent]:
    detail_url_template = str(config.adapters["eastmoney"]["detail_url"])
    current_date = today or datetime.now(config.timezone).date()
    cutoff = current_date - timedelta(days=config.event_lookback_days)
    events: list[BondEvent] = []

    for index, row in enumerate(raw_rows, start=1):
        code = row.get("SECURITY_CODE")
        name = row.get("SECURITY_NAME_ABBR")
        if not isinstance(code, str) or not code.strip() or not isinstance(name, str) or not name.strip():
            print(f"Warning: skip Eastmoney item #{index}, missing SECURITY_CODE/SECURITY_NAME_ABBR: {row!r}", file=sys.stderr)
            continue

        detail_url = detail_url_template.format(code=code.strip())
        description_fields = tuple(line for line in eastmoney_description_fields(row) if line)

        for field, event_type in (
            ("PUBLIC_START_DATE", "subscribe"),
            ("BOND_START_DATE", "ballot"),
            ("LISTING_DATE", "list"),
        ):
            event_date = parse_event_date(row.get(field))
            if event_date is None or event_date < cutoff:
                continue
            events.append(
                BondEvent(
                    code=code.strip(),
                    name=name.strip(),
                    event_type=event_type,
                    event_date=event_date,
                    detail_url=detail_url,
                    description_fields=description_fields,
                    source="东方财富",
                )
            )

    return events


def eastmoney_description_fields(row: dict[str, Any]) -> list[str | None]:
    stock_code = row.get("CONVERT_STOCK_CODE")
    stock_name = row.get("SECURITY_SHORT_NAME")
    stock_line = None
    if not is_empty_value(stock_code) and not is_empty_value(stock_name):
        stock_line = f"正股: {stock_name}({stock_code})"
    elif not is_empty_value(stock_code):
        stock_line = f"正股: {stock_code}"
    elif not is_empty_value(stock_name):
        stock_line = f"正股: {stock_name}"

    return [
        optional_line("申购", row.get("CORRECODE")),
        stock_line,
        compact_join(
            [
                optional_line("登记", format_event_date(row.get("SECURITY_START_DATE"))),
                optional_line("配售", format_preplacing(row.get("FIRST_PER_PREPLACING"))),
            ]
        ),
        compact_join(
            [
                optional_line("规模", format_scale(row.get("ACTUAL_ISSUE_SCALE"))),
                optional_line("评级", row.get("RATING")),
            ]
        ),
        optional_line("中签率", format_percent(row.get("ONLINE_GENERAL_LWR"))),
        "来源: 东方财富",
    ]
