import sys
import unittest
from pathlib import Path
from unittest.mock import patch


STUDIP_DIR = Path(__file__).resolve().parents[1] / "mcps" / "studip"
sys.path.insert(0, str(STUDIP_DIR))

import studip_client


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


class DateRangeTests(unittest.TestCase):
    def test_inclusive_date_filter_includes_entire_end_date(self):
        start = studip_client._parse_date("2026-11-13", "start_date")
        end = studip_client._parse_date("2026-11-13", "end_date")

        self.assertTrue(
            studip_client._date_in_range(
                "2026-11-13T23:59:00+01:00",
                start,
                end,
                start_is_date=True,
                end_is_date=True,
            )
        )

    def test_date_filter_excludes_items_without_dates(self):
        start = studip_client._parse_date("2026-11-13", "start_date")
        self.assertFalse(
            studip_client._date_in_range(None, start, None, start_is_date=True)
        )


class SemesterStartTests(unittest.TestCase):
    def test_infers_winter_and_summer_starts(self):
        self.assertEqual(studip_client._semester_start_date("WiSe 2026/27"), "2026-10-01")
        self.assertEqual(studip_client._semester_start_date("SS 2027"), "2027-04-01")

    def test_rejects_unknown_semester_title(self):
        with self.assertRaises(ValueError):
            studip_client._semester_start_date("Fall Term 2027")


class PaginationTests(unittest.TestCase):
    def test_follows_next_link_until_collection_is_complete(self):
        first_page = {
            "data": [{"id": "first"}],
            "links": {
                "next": (
                    "https://studip.example.edu/jsonapi.php/v1/"
                    "courses?page%5Boffset%5D=1"
                )
            },
        }
        second_page = {"data": [{"id": "second"}], "links": {"next": None}}

        with patch(
            "studip_client._get",
            side_effect=[FakeResponse(first_page), FakeResponse(second_page)],
        ) as get:
            result = studip_client._fetch_all(
                "courses", {"page[limit]": 1}
            )

        self.assertEqual([item["id"] for item in result], ["first", "second"])
        self.assertEqual(get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
