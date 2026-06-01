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
        self.assertIn("TRIGGER:-PT5M", listing)
        self.assertIn("TRIGGER:PT1H30M", listing)
        self.assertIn("TRIGGER:PT4H", listing)
        self.assertNotIn("TRIGGER:PT3H", listing)

    def test_serialization_is_stable(self) -> None:
        filtered = main.filter_bond_events(self.raw_events)

        first = main.stable_calendar_text(main.build_calendar(filtered))
        second = main.stable_calendar_text(main.build_calendar(filtered))

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

        events = main.build_eastmoney_events(rows, today=main.date(2026, 6, 1))
        calendar_text = main.stable_calendar_text(main.build_calendar(events))

        self.assertEqual(["申购日", "中签公布", "上市日"], [item["keyword"] for item in events])
        self.assertIn("SUMMARY:【申购日】通合转债", calendar_text)
        self.assertIn("SUMMARY:【中签公布】通合转债", calendar_text)
        self.assertIn("SUMMARY:【上市日】通合转债", calendar_text)
        self.assertIn("UID:123271-subscribe-2026-06-02@bond-calendar", calendar_text)
        self.assertIn("UID:123271-payment-2026-06-04@bond-calendar", calendar_text)
        self.assertIn("UID:123271-list-2026-06-20@bond-calendar", calendar_text)
        self.assertIn("申购代码: 370491", calendar_text)
        self.assertIn("股权登记日: 2026-06-01", calendar_text)
        self.assertIn("发行规模: 5.219327亿元", calendar_text)
        self.assertIn("中签率: 0.0012%", calendar_text)
        self.assertIn("信用评级: AA", calendar_text)
        self.assertIn("正股: 通合科技(300491)", calendar_text)
        self.assertIn("数据来源: 东方财富", calendar_text)

    def test_ballot_announcement_alarm_rules(self) -> None:
        rows = [
            {
                "SECURITY_CODE": "123271",
                "SECURITY_NAME_ABBR": "通合转债",
                "BOND_START_DATE": "2026-06-04 00:00:00",
            }
        ]

        events = main.build_eastmoney_events(rows, today=main.date(2026, 6, 1))
        calendar_text = main.stable_calendar_text(main.build_calendar(events))
        payment = event_block(calendar_text, "123271-payment-2026-06-04@bond-calendar")

        self.assertIn("TRIGGER:PT1H", payment)
        self.assertIn("TRIGGER:PT3H30M", payment)
        self.assertNotIn("TRIGGER:-P1D", payment)
        self.assertNotIn("TRIGGER:-PT30M", payment)

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

        events = main.build_eastmoney_events(rows, today=main.date(2026, 6, 1))

        self.assertEqual(["123271", "123271"], [item["code"] for item in events])
        self.assertEqual(["申购日", "中签公布"], [item["keyword"] for item in events])

    def test_load_events_falls_back_to_jisilu(self) -> None:
        original_eastmoney = main.fetch_eastmoney_bond_data
        original_jisilu = main.fetch_jisilu_calendar_data
        try:
            main.fetch_eastmoney_bond_data = lambda: None
            main.fetch_jisilu_calendar_data = lambda: self.raw_events

            loaded = main.load_matched_events(today=main.date(2026, 6, 1))

            self.assertIsNotNone(loaded)
            matched_events, raw_count, source = loaded
            self.assertEqual(3, raw_count)
            self.assertEqual("集思录兜底", source)
            self.assertEqual(["申购日", "上市日"], [item["keyword"] for item in matched_events])
        finally:
            main.fetch_eastmoney_bond_data = original_eastmoney
            main.fetch_jisilu_calendar_data = original_jisilu


if __name__ == "__main__":
    unittest.main()
