from __future__ import annotations

from datetime import datetime

from .adapters import resolve_adapter
from .ics_writer import build_calendar, event_title, sorted_events, write_calendar
from .models import AdapterResult, BondEvent, CalendarConfig


def load_events(config: CalendarConfig) -> AdapterResult | None:
    today = datetime.now(config.timezone).date()

    for source in config.sources:
        settings = config.adapters.get(source, {})
        try:
            adapter_class = resolve_adapter(source, settings)
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            print(f"Warning: cannot load data source strategy {source!r}: {exc}")
            continue
        if adapter_class is None:
            print(f"Warning: unknown data source strategy {source!r}, skip.")
            continue

        result = adapter_class().fetch(config, today=today)
        if result and result.events:
            return result
        if result:
            print(f"Warning: {result.source} returned no usable calendar events, try next source.")

    return None


def generate_calendar(config: CalendarConfig) -> AdapterResult | None:
    result = load_events(config)
    if result is None:
        return None

    calendar = build_calendar(list(result.events), config)
    write_calendar(calendar, config.output_file)
    return result


def print_event_summary(items: tuple[BondEvent, ...], config: CalendarConfig) -> None:
    if not items:
        return

    print("Matched bond events:")
    for item in sorted_events(list(items), config):
        print(f"- {item.event_date.isoformat()} {item.code} {event_title(item, config)}")
