from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from bond_calendar.adapters.eastmoney import build_eastmoney_events
from bond_calendar.adapters import resolve_adapter
from bond_calendar.adapters.eastmoney import EastmoneyAdapter
from bond_calendar.adapters.jisilu import build_jisilu_events
from bond_calendar.config import load_config
from bond_calendar.ics_writer import build_calendar, stable_calendar_text
from bond_calendar.models import BondEvent


def event_block(calendar_text: str, uid: str) -> str:
    for block in calendar_text.split("BEGIN:VEVENT")[1:]:
        text = "BEGIN:VEVENT" + block
        if f"UID:{uid}" in text:
            return text
    raise AssertionError(f"Missing event block for {uid}")


class CalendarRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config()
        self.jisilu_raw_events = [
            {
                "id": "CNV10001",
                "code": "123271",
                "title": "【申购日】通合转债",
                "start": "2026-06-02",
                "description": "转债代码:123271<br>申购代码:370491<br>",
                "url": "/data/convert_bond_detail/123271",
            },
            {
                "id": "CNV10002",
                "code": "123999",
                "title": "【上市日】测试转债",
                "start": "2026-06-03",
                "description": "转债代码:123999<br>",
                "url": "/data/convert_bond_detail/123999",
            },
            {
                "id": "CNV10003",
                "code": "118033",
                "title": "【最后交易日】华特转债",
                "start": "2026-06-04",
                "description": "转债代码:118033<br>",
                "url": "/data/convert_bond_detail/118033",
            },
        ]

    def test_load_config_supports_env_and_cli_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "custom.ics"
            original_output = os.environ.get("BOND_CALENDAR_OUTPUT")
            original_source = os.environ.get("BOND_CALENDAR_SOURCE")
            try:
                os.environ["BOND_CALENDAR_OUTPUT"] = str(output_path)
                os.environ["BOND_CALENDAR_SOURCE"] = "jisilu"

                config = load_config(output_file="cli.ics", source="eastmoney")

                self.assertEqual(Path("cli.ics"), config.output_file)
                self.assertEqual(("eastmoney",), config.sources)
                self.assertIn("subscribe", config.event_rules)
            finally:
                restore_env("BOND_CALENDAR_OUTPUT", original_output)
                restore_env("BOND_CALENDAR_SOURCE", original_source)

    def test_bond_event_requires_standard_fields(self) -> None:
        with self.assertRaises(ValueError):
            BondEvent(code="", name="通合转债", event_type="subscribe", event_date=date(2026, 6, 2))
        with self.assertRaises(ValueError):
            BondEvent(code="123271", name="通合转债", event_type="unknown", event_date=date(2026, 6, 2))

    def test_adapter_strategy_can_be_resolved_from_config_class_path(self) -> None:
        adapter_class = resolve_adapter(
            "custom_eastmoney",
            {"class": "bond_calendar.adapters.eastmoney:EastmoneyAdapter"},
        )

        self.assertIs(EastmoneyAdapter, adapter_class)

    def test_jisilu_adapter_keeps_subscription_and_listing_events(self) -> None:
        events = build_jisilu_events(self.jisilu_raw_events, self.config, today=date(2026, 6, 1))

        self.assertEqual(["subscribe", "list"], [item.event_type for item in events])
        self.assertEqual(["通合转债", "测试转债"], [item.name for item in events])

    def test_stable_uid_and_short_event_duration(self) -> None:
        events = build_jisilu_events(self.jisilu_raw_events, self.config, today=date(2026, 6, 1))
        calendar_text = stable_calendar_text(build_calendar(events, self.config))

        self.assertIn("UID:123271-subscribe-2026-06-02@bond-calendar", calendar_text)
        self.assertIn("UID:123999-list-2026-06-03@bond-calendar", calendar_text)
        self.assertNotIn("CNV10001", calendar_text)
        self.assertIn("DTSTART:20260602T013000Z", calendar_text)
        self.assertIn("DTEND:20260602T013500Z", calendar_text)

    def test_alarm_rules(self) -> None:
        events = build_jisilu_events(self.jisilu_raw_events, self.config, today=date(2026, 6, 1))
        calendar_text = stable_calendar_text(build_calendar(events, self.config))
        subscribe = event_block(calendar_text, "123271-subscribe-2026-06-02@bond-calendar")
        listing = event_block(calendar_text, "123999-list-2026-06-03@bond-calendar")

        self.assertIn("TRIGGER:PT30M", subscribe)
        self.assertIn("TRIGGER:PT3H", subscribe)
        self.assertNotIn("TRIGGER:-P1D", subscribe)

        self.assertIn("TRIGGER:-P1D", listing)
        self.assertIn("TRIGGER:-PT5M", listing)
        self.assertIn("TRIGGER:PT1H30M", listing)
        self.assertIn("TRIGGER:PT4H", listing)

    def test_serialization_is_stable(self) -> None:
        events = build_jisilu_events(self.jisilu_raw_events, self.config, today=date(2026, 6, 1))

        first = stable_calendar_text(build_calendar(events, self.config))
        second = stable_calendar_text(build_calendar(events, self.config))

        self.assertEqual(first, second)

    def test_builds_eastmoney_events_with_ballot_announcement(self) -> None:
        rows = [
            {
                "SECURITY_CODE": "123271",
                "SECURITY_NAME_ABBR": "通合转债",
                "CORRECODE": "370491",
                "PUBLIC_START_DATE": "2026-06-02 00:00:00",
                "BOND_START_DATE": "2026-06-04 00:00:00",
                "LISTING_DATE": "2026-06-20 00:00:00",
                "SECURITY_START_DATE": "2026-06-01 00:00:00",
                "FIRST_PER_PREPLACING": "2.9377",
                "ACTUAL_ISSUE_SCALE": "5.219327",
                "ONLINE_GENERAL_LWR": "0.0012",
                "RATING": "AA",
                "CONVERT_STOCK_CODE": "300491",
                "SECURITY_SHORT_NAME": "通合科技",
            }
        ]

        events = build_eastmoney_events(rows, self.config, today=date(2026, 6, 1))
        calendar_text = stable_calendar_text(build_calendar(events, self.config))

        self.assertEqual(["subscribe", "ballot", "list"], [item.event_type for item in events])
        self.assertIn("SUMMARY:【申购日】通合转债", calendar_text)
        self.assertIn("SUMMARY:【中签公布】通合转债", calendar_text)
        self.assertIn("SUMMARY:【上市日】通合转债", calendar_text)
        self.assertIn("UID:123271-subscribe-2026-06-02@bond-calendar", calendar_text)
        self.assertIn("UID:123271-payment-2026-06-04@bond-calendar", calendar_text)
        self.assertIn("UID:123271-list-2026-06-20@bond-calendar", calendar_text)
        self.assertIn("申购: 370491", calendar_text)
        self.assertIn("登记: 2026-06-01", calendar_text)
        self.assertIn("配售: 2.9377/股", calendar_text)
        self.assertIn("规模: 5.22亿", calendar_text)
        self.assertIn("中签率: 0.0012%", calendar_text)
        self.assertIn("评级: AA", calendar_text)
        self.assertIn("正股: 通合科技(300491)", calendar_text)
        self.assertIn("来源: 东方财富", calendar_text)

    def test_ballot_announcement_alarm_rules(self) -> None:
        rows = [
            {
                "SECURITY_CODE": "123271",
                "SECURITY_NAME_ABBR": "通合转债",
                "BOND_START_DATE": "2026-06-04 00:00:00",
            }
        ]

        events = build_eastmoney_events(rows, self.config, today=date(2026, 6, 1))
        calendar_text = stable_calendar_text(build_calendar(events, self.config))
        payment = event_block(calendar_text, "123271-payment-2026-06-04@bond-calendar")

        self.assertIn("TRIGGER:PT1H", payment)
        self.assertIn("TRIGGER:PT3H30M", payment)
        self.assertNotIn("TRIGGER:-P1D", payment)

    def test_eastmoney_events_skip_old_dates(self) -> None:
        rows = [
            {
                "SECURITY_CODE": "123269",
                "SECURITY_NAME_ABBR": "金杨转债",
                "PUBLIC_START_DATE": "2026-04-20 00:00:00",
                "BOND_START_DATE": "2026-04-22 00:00:00",
                "LISTING_DATE": "2026-05-11 00:00:00",
            },
            {
                "SECURITY_CODE": "123271",
                "SECURITY_NAME_ABBR": "通合转债",
                "PUBLIC_START_DATE": "2026-06-02 00:00:00",
                "BOND_START_DATE": "2026-06-04 00:00:00",
            },
        ]

        events = build_eastmoney_events(rows, self.config, today=date(2026, 6, 1))

        self.assertEqual(["123271", "123271"], [item.code for item in events])
        self.assertEqual(["subscribe", "ballot"], [item.event_type for item in events])


def restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
