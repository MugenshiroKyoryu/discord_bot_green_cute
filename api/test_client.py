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
    _cache_get,
    _cache_put,
    _clean_query,
    _detail_cache,
    _error_detail,
    _format_context,
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

    def test_returns_a_copy_so_callers_can_add_hit_title(self):
        _cache_put(1, {"title": "One Piece"})
        first = _cache_get(1)
        first["hit_title"] = "Wan Pisu"
        self.assertNotIn("hit_title", _cache_get(1))

    def test_expired_entry_is_dropped(self):
        _detail_cache[1] = (time.monotonic() - _DETAIL_TTL - 1, {"title": "One Piece"})
        self.assertIsNone(_cache_get(1))
        self.assertNotIn(1, _detail_cache)


if __name__ == "__main__":
    unittest.main()
