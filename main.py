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


JISILU_CALENDAR_URL = "https://www.jisilu.cn/data/calendar/get_calendar_data/?qtype=CNV"
JISILU_BASE_URL = "https://www.jisilu.cn"
EASTMONEY_API_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EASTMONEY_PAGE_URL = "https://data.eastmoney.com/xg/xg/?mkt=kzz"
EASTMONEY_DETAIL_URL = "https://data.eastmoney.com/kzz/detail/{code}.html"
OUTPUT_FILE = Path("kzz.ics")
TIMEZONE = ZoneInfo("Asia/Shanghai")
EVENT_LOOKBACK_DAYS = 7

EVENT_KEYWORDS = [
    "申购日",
    "中签公布",
    "上市日",
]

EVENT_UID_TYPES = {
    "申购日": "subscribe",
    "中签公布": "payment",
    "上市日": "list",
}

EASTMONEY_EVENT_FIELDS = (
    ("PUBLIC_START_DATE", "申购日"),
    ("BOND_START_DATE", "中签公布"),
    ("LISTING_DATE", "上市日"),
)

EVENT_START_TIME = clock_time(9, 30)
EVENT_DURATION = timedelta(minutes=5)
ALARM_RULES = {
    "申购日": (
        timedelta(minutes=30),  # 10:00
        timedelta(hours=3),  # 12:30
    ),
    "中签公布": (
        timedelta(hours=1),  # 10:30
        timedelta(hours=3, minutes=30),  # 13:00
    ),
    "上市日": (
        timedelta(days=-1),
        timedelta(minutes=-5),  # 09:25
        timedelta(hours=1, minutes=30),  # 11:00
        timedelta(hours=4),  # 13:30
    ),
}

JISILU_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.jisilu.cn/data/calendar/",
}

EASTMONEY_HEADERS = {
    "User-Agent": JISILU_HEADERS["User-Agent"],
    "Accept": "application/json,text/plain,*/*",
    "Referer": EASTMONEY_PAGE_URL,
}


def fetch_eastmoney_bond_data(retries: int = 3, timeout: int = 15, page_size: int = 500) -> list[dict[str, Any]] | None:
    """Fetch convertible bond list data from Eastmoney. Return None on upstream failure."""
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            rows: list[dict[str, Any]] = []
            page = 1
            total_pages = 1

            while page <= total_pages:
                response = requests.get(
                    EASTMONEY_API_URL,
                    headers=EASTMONEY_HEADERS,
                    params={
                        "reportName": "RPT_BOND_CB_LIST",
                        "columns": "ALL",
                        "source": "WEB",
                        "client": "WEB",
                        "pageNumber": str(page),
                        "pageSize": str(page_size),
                        "sortColumns": "PUBLIC_START_DATE,SECURITY_CODE",
                        "sortTypes": "-1,1",
                    },
                    timeout=timeout,
                )
                response.raise_for_status()
                payload = response.json()
                page_rows, total_pages = parse_eastmoney_payload(payload, page_size)
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

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        if isinstance(item, dict):
            rows.append(item)
        else:
            print(f"Warning: skip Eastmoney item #{index}, expected object: {item!r}", file=sys.stderr)

    pages = result.get("pages")
    if isinstance(pages, int) and pages > 0:
        return rows, pages

    count = result.get("count")
    if isinstance(count, int) and count > 0:
        return rows, max(1, (count + page_size - 1) // page_size)

    return rows, 1


def fetch_jisilu_calendar_data(retries: int = 3, timeout: int = 15) -> list[dict[str, Any]] | None:
    """Fetch Jisilu convertible bond calendar data. Return None on upstream failure."""
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(JISILU_CALENDAR_URL, headers=JISILU_HEADERS, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError(f"Expected JSON list, got {type(data).__name__}")
            events: list[dict[str, Any]] = []
            for index, item in enumerate(data, start=1):
                if isinstance(item, dict):
                    events.append(item)
                else:
                    print(f"Warning: skip Jisilu item #{index}, expected object: {item!r}", file=sys.stderr)
            return events
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            print(f"Warning: Jisilu fetch attempt {attempt}/{retries} failed: {exc}", file=sys.stderr)
            if attempt < retries:
                time.sleep(2 ** (attempt - 1))

    print(f"Warning: upstream calendar fetch failed, keep existing {OUTPUT_FILE}: {last_error}", file=sys.stderr)
    return None


def today_in_timezone() -> date:
    return datetime.now(TIMEZONE).date()


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


def format_event_date(value: Any) -> str | None:
    event_date = parse_event_date(value)
    if event_date is None:
        return None
    return event_date.isoformat()


def is_empty_value(value: Any) -> bool:
    return value is None or value == "" or value == "-"


def format_percent(value: Any) -> str | None:
    if is_empty_value(value):
        return None
    return f"{value}%"


def format_scale(value: Any) -> str | None:
    if is_empty_value(value):
        return None
    return f"{value}亿元"


def optional_line(label: str, value: Any) -> str | None:
    if is_empty_value(value):
        return None
    return f"{label}: {value}"


def clean_description(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def is_in_event_window(event_date: date, today: date | None = None) -> bool:
    current_date = today or today_in_timezone()
    return event_date >= current_date - timedelta(days=EVENT_LOOKBACK_DAYS)


def eastmoney_detail_url(code: str) -> str:
    return EASTMONEY_DETAIL_URL.format(code=code)


def eastmoney_description(row: dict[str, Any], detail_url: str) -> str:
    stock_code = row.get("CONVERT_STOCK_CODE")
    stock_name = row.get("SECURITY_SHORT_NAME")
    stock_line = None
    if not is_empty_value(stock_code) and not is_empty_value(stock_name):
        stock_line = f"正股: {stock_name}({stock_code})"
    elif not is_empty_value(stock_code):
        stock_line = f"正股代码: {stock_code}"
    elif not is_empty_value(stock_name):
        stock_line = f"正股简称: {stock_name}"

    lines = [
        optional_line("申购代码", row.get("CORRECODE")),
        optional_line("股权登记日", format_event_date(row.get("SECURITY_START_DATE"))),
        optional_line("每股配售额", row.get("FIRST_PER_PREPLACING")),
        optional_line("发行规模", format_scale(row.get("ACTUAL_ISSUE_SCALE"))),
        optional_line("中签率", format_percent(row.get("ONLINE_GENERAL_LWR"))),
        optional_line("信用评级", row.get("RATING")),
        stock_line,
        "数据来源: 东方财富",
    ]
    return "\n".join(line for line in lines if line)


def build_eastmoney_events(raw_rows: list[dict[str, Any]], today: date | None = None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for index, row in enumerate(raw_rows, start=1):
        code = row.get("SECURITY_CODE")
        name = row.get("SECURITY_NAME_ABBR")
        if not isinstance(code, str) or not code.strip() or not isinstance(name, str) or not name.strip():
            print(f"Warning: skip Eastmoney item #{index}, missing SECURITY_CODE/SECURITY_NAME_ABBR: {row!r}", file=sys.stderr)
            continue

        detail_url = eastmoney_detail_url(code.strip())
        description = eastmoney_description(row, detail_url)

        for field, keyword in EASTMONEY_EVENT_FIELDS:
            event_date = parse_event_date(row.get(field))
            if event_date is None or not is_in_event_window(event_date, today):
                continue
            events.append(
                {
                    "id": None,
                    "title": f"【{keyword}】{name.strip()}",
                    "code": code.strip(),
                    "date": event_date,
                    "keyword": keyword,
                    "description": description,
                    "url": detail_url,
                    "source": "东方财富",
                }
            )

    return events


def filter_jisilu_bond_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
                "source": "集思录",
            }
        )

    return filtered


def filter_bond_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return filter_jisilu_bond_events(raw_events)


def load_matched_events(today: date | None = None) -> tuple[list[dict[str, Any]], int, str] | None:
    eastmoney_rows = fetch_eastmoney_bond_data()
    if eastmoney_rows:
        eastmoney_events = build_eastmoney_events(eastmoney_rows, today)
        if eastmoney_events:
            return eastmoney_events, len(eastmoney_rows), "东方财富"
        print("Warning: Eastmoney returned no usable calendar events, fallback to Jisilu.", file=sys.stderr)
    else:
        print("Warning: Eastmoney returned no raw rows, fallback to Jisilu.", file=sys.stderr)

    jisilu_events = fetch_jisilu_calendar_data()
    if jisilu_events is None:
        return None

    return filter_jisilu_bond_events(jisilu_events), len(jisilu_events), "集思录兜底"


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
            f"详情页: {detail_url}",
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
    loaded = load_matched_events()
    if loaded is None:
        return 0

    matched_events, raw_count, source = loaded
    if not matched_events:
        print("No matched bond events found.")

    calendar = build_calendar(matched_events)
    write_calendar(calendar)
    print(f"Fetched {raw_count} raw events from {source}, wrote {len(matched_events)} matched events to {OUTPUT_FILE}.")
    print_event_summary(matched_events)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
