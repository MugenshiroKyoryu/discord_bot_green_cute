#!/usr/bin/env python3
"""เทสต์ส่วนที่ไม่ต้องต่อเน็ตของ api/_client.py

ตัวอย่าง error body ถอดจาก 400 จริงที่ MangaUpdates ส่งกลับมา
ต้องรันด้วย python ใน .venv เพราะ _client import aiohttp

    .venv/Scripts/python -m unittest discover -s api -p "test_*.py" -v
"""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api._client import (  # noqa: E402
    _DETAIL_TTL,
    _MAX_RELATED,
    _cache_get,
    _cache_put,
    _clean_query,
    _detail_cache,
    _error_detail,
    _format_context,
    _related_to_fetch,
)


class _FakeResponse:
    """พอสำหรับ _error_detail ซึ่งใช้แค่ status กับ json()"""

    def __init__(self, status, payload=None, raises=None):
        self.status = status
        self._payload = payload
        self._raises = raises

    async def json(self, content_type=None):
        if self._raises is not None:
            raise self._raises
        return self._payload


class CleanQueryTests(unittest.TestCase):

    def test_trims_whitespace(self):
        self.assertEqual(_clean_query("  one piece  "), "one piece")

    def test_rejects_empty_query(self):
        # ไม่งั้นจะเสีย request ไปแลกกับ 400 เปล่า ๆ
        with self.assertRaises(Exception):
            _clean_query("   ")

    def test_rejects_query_longer_than_spec_allows(self):
        with self.assertRaises(Exception):
            _clean_query("a" * 401)

    def test_accepts_query_at_the_limit(self):
        self.assertEqual(len(_clean_query("a" * 400)), 400)


class ErrorDetailTests(unittest.TestCase):

    # body จริงจาก {"search": "naruto", "filters": ["nope"]}
    VALIDATION_BODY = {
        "status": "exception",
        "reason": "Field Validation Error",
        "context": {
            "filters": [
                {"index": 0, "errors": ['"nope" must be in `{ "scanlated", "completed", ... }`']}
            ]
        },
    }

    def test_formats_field_validation_error(self):
        detail = asyncio.run(_error_detail(_FakeResponse(400, self.VALIDATION_BODY)))
        self.assertIn("Field Validation Error", detail)
        self.assertIn("filters", detail)
        self.assertIn("must be in", detail)

    def test_keeps_reason_when_there_is_no_context(self):
        body = {"status": "exception", "reason": "Series not found"}
        detail = asyncio.run(_error_detail(_FakeResponse(404, body)))
        self.assertEqual(detail, "404 Series not found")

    def test_falls_back_to_status_when_body_is_not_json(self):
        resp = _FakeResponse(502, raises=ValueError("not json"))
        self.assertEqual(asyncio.run(_error_detail(resp)), "502")

    def test_falls_back_to_status_when_body_has_no_reason(self):
        detail = asyncio.run(_error_detail(_FakeResponse(500, {"oops": True})))
        self.assertEqual(detail, "500")

    def test_format_context_reads_first_error_of_each_field(self):
        context = {"perpage": [{"index": 0, "errors": ["0 must be greater than 0"]}]}
        self.assertEqual(_format_context(context), ["perpage: 0 must be greater than 0"])


class DetailCacheTests(unittest.TestCase):

    def setUp(self):
        _detail_cache.clear()
        self.addCleanup(_detail_cache.clear)

    def test_round_trip(self):
        _cache_put(1, {"title": "One Piece"})
        self.assertEqual(_cache_get(1), {"title": "One Piece"})

    def test_miss_returns_none(self):
        self.assertIsNone(_cache_get(999))

    def test_returns_a_copy_so_callers_can_add_total_hits(self):
        _cache_put(1, {"title": "One Piece"})
        first = _cache_get(1)
        first["total_hits"] = 8900
        self.assertNotIn("total_hits", _cache_get(1))

    def test_expired_entry_is_dropped(self):
        _detail_cache[1] = (time.monotonic() - _DETAIL_TTL - 1, {"title": "One Piece"})
        self.assertIsNone(_cache_get(1))
        self.assertNotIn(1, _detail_cache)


class RelatedToFetchTests(unittest.TestCase):
    """related_series จริงของ Konjiki no Word Master (id 67937814952)"""

    KONJIKI = {
        "title": "Konjiki no Word Master: Yuusha Yonin ni Makikomareta Unique Cheat",
        "related": [
            {
                "id": 17505874636,
                "relation": "Adapted From",
                "name": "Konjiki no Moji Tsukai (Novel)",
            }
        ],
    }

    def test_picks_the_novel_the_manga_was_adapted_from(self):
        self.assertEqual(
            _related_to_fetch(self.KONJIKI, set()),
            [(17505874636, "Adapted From")],
        )

    def test_skips_series_already_in_the_results(self):
        # ผลค้นหาพานิยายมาเองแล้ว ไม่ต้องยิง detail ซ้ำ
        self.assertEqual(_related_to_fetch(self.KONJIKI, {17505874636}), [])

    def test_does_not_touch_the_set_it_was_given(self):
        seen = {67937814952}
        _related_to_fetch(self.KONJIKI, seen)
        self.assertEqual(seen, {67937814952})

    def test_skips_relations_that_are_a_different_story(self):
        # ภาคต่อกับ spin-off เป็นคนละเรื่อง ผู้ใช้ไม่ได้ค้นหา
        detail = {
            "related": [
                {"id": 1, "relation": "Sequel", "name": "ภาคต่อ"},
                {"id": 2, "relation": "Spin-Off", "name": "ภาคแยก"},
                {"id": 3, "relation": "Other", "name": "อื่น ๆ"},
            ]
        }
        self.assertEqual(_related_to_fetch(detail, set()), [])

    def test_respects_the_limit(self):
        detail = {
            "related": [
                {"id": i, "relation": "Alternate Version", "name": f"เวอร์ชัน {i}"}
                for i in range(1, _MAX_RELATED + 5)
            ]
        }
        self.assertEqual(len(_related_to_fetch(detail, set())), _MAX_RELATED)

    def test_drops_duplicate_ids_inside_related(self):
        detail = {
            "related": [
                {"id": 7, "relation": "Adapted From", "name": "นิยาย"},
                {"id": 7, "relation": "Main Story", "name": "นิยาย"},
            ]
        }
        self.assertEqual(_related_to_fetch(detail, set()), [(7, "Adapted From")])

    def test_handles_series_without_related_data(self):
        # API ส่ง null มาทั้งที่มี key ได้ และเรื่องส่วนใหญ่ไม่มีความสัมพันธ์เลย
        self.assertEqual(_related_to_fetch({}, set()), [])
        self.assertEqual(_related_to_fetch({"related": None}, set()), [])


if __name__ == "__main__":
    unittest.main()
