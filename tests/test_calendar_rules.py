from __future__ import annotations

import unittest

import main


def event_block(calendar_text: str, uid: str) -> str:
    for block in calendar_text.split("BEGIN:VEVENT")[1:]:
        text = "BEGIN:VEVENT" + block
        if f"UID:{uid}" in text:
            return text
    raise AssertionError(f"Missing event block for {uid}")


class CalendarRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_events = [
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

    def test_filters_only_subscription_and_listing_events(self) -> None:
        filtered = main.filter_bond_events(self.raw_events)

        self.assertEqual(["申购日", "上市日"], [item["keyword"] for item in filtered])
        self.assertNotIn("最后交易日", [item["keyword"] for item in filtered])

    def test_stable_uid_and_short_event_duration(self) -> None:
        calendar_text = main.stable_calendar_text(main.build_calendar(main.filter_bond_events(self.raw_events)))

        self.assertIn("UID:123271-subscribe-2026-06-02@bond-calendar", calendar_text)
        self.assertIn("UID:123999-list-2026-06-03@bond-calendar", calendar_text)
        self.assertNotIn("CNV10001", calendar_text)
        self.assertIn("DTSTART:20260602T013000Z", calendar_text)
        self.assertIn("DTEND:20260602T013500Z", calendar_text)

    def test_alarm_rules(self) -> None:
        calendar_text = main.stable_calendar_text(main.build_calendar(main.filter_bond_events(self.raw_events)))
        subscribe = event_block(calendar_text, "123271-subscribe-2026-06-02@bond-calendar")
        listing = event_block(calendar_text, "123999-list-2026-06-03@bond-calendar")

        self.assertIn("TRIGGER:PT30M", subscribe)
        self.assertIn("TRIGGER:PT3H", subscribe)
        self.assertNotIn("TRIGGER:-P1D", subscribe)
        self.assertNotIn("TRIGGER:-PT30M", subscribe)

        self.assertIn("TRIGGER:-P1D", listing)
        self.assertIn("TRIGGER:-PT30M", listing)
        self.assertNotIn("TRIGGER:PT3H", listing)

    def test_serialization_is_stable(self) -> None:
        filtered = main.filter_bond_events(self.raw_events)

        first = main.stable_calendar_text(main.build_calendar(filtered))
        second = main.stable_calendar_text(main.build_calendar(filtered))

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
