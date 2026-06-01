from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any


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


def format_decimal(value: Any, digits: int) -> str | None:
    if is_empty_value(value):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return str(value)

    quantizer = Decimal("1") if digits == 0 else Decimal("0." + "0" * (digits - 1) + "1")
    return f"{number.quantize(quantizer):f}".rstrip("0").rstrip(".")


def format_percent(value: Any) -> str | None:
    formatted = format_decimal(value, 4)
    if formatted is None:
        return None
    return f"{formatted}%"


def format_scale(value: Any) -> str | None:
    formatted = format_decimal(value, 2)
    if formatted is None:
        return None
    return f"{formatted}亿"


def format_preplacing(value: Any) -> str | None:
    formatted = format_decimal(value, 4)
    if formatted is None:
        return None
    return f"{formatted}/股"


def optional_line(label: str, value: Any) -> str | None:
    if is_empty_value(value):
        return None
    return f"{label}: {value}"


def compact_join(parts: list[str | None], separator: str = " | ") -> str | None:
    values = [part for part in parts if part]
    if not values:
        return None
    return separator.join(values)


def parse_duration(value: str) -> timedelta:
    negative = value.startswith("-")
    text = value[1:] if negative else value
    if text.startswith("P") and not text.startswith("PT"):
        amount = int(text[1:-1])
        delta = timedelta(days=amount)
    elif text.startswith("PT"):
        hours = 0
        minutes = 0
        rest = text[2:]
        if "H" in rest:
            hour_text, rest = rest.split("H", 1)
            hours = int(hour_text)
        if "M" in rest:
            minute_text = rest.split("M", 1)[0]
            minutes = int(minute_text)
        delta = timedelta(hours=hours, minutes=minutes)
    else:
        raise ValueError(f"Unsupported duration: {value!r}")
    return -delta if negative else delta

