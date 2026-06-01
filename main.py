from __future__ import annotations

import argparse

from bond_calendar.config import DEFAULT_CONFIG_FILE, load_config
from bond_calendar.pipeline import generate_calendar, print_event_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate convertible bond reminder ICS.")
    parser.add_argument("--config", default=None, help=f"Config file path. Default: {DEFAULT_CONFIG_FILE}")
    parser.add_argument("--output", default=None, help="Output ICS file path.")
    parser.add_argument("--source", default=None, help="Comma-separated data sources, for example: eastmoney,jisilu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(config_file=args.config, output_file=args.output, source=args.source)
    result = generate_calendar(config)
    if result is None:
        print(f"No usable events found; keep existing {config.output_file}.")
        return 0

    print(f"Fetched {result.raw_count} raw events from {result.source}, wrote {len(result.events)} matched events to {config.output_file}.")
    print_event_summary(result.events, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
