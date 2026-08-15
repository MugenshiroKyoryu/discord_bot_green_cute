#!/usr/bin/env python3
"""เทสต์การจัดอันดับผลค้นหา

ใช้ unittest ของ stdlib ตามที่โปรเจกต์ทำอยู่ ไม่เพิ่ม dependency
ข้อมูลตัวอย่างถอดจากผลจริงของ POST /series/search ตอนพัฒนา จะได้เทสกับ
เคสที่พลาดจริง ไม่ใช่เคสที่แต่งให้ผ่าน

    python -m unittest discover -s api -p "test_*.py" -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api._ranking import MATCH_FLOOR, normalize, rank, score_item  # noqa: E402


def _item(title, hit_title=None, series_id=1, votes=0, rating=None):
    """ผลลัพธ์ 1 รายการตามรูปของ SeriesSearchResponseV1.results"""
    return {
        "record": {
            "series_id": series_id,
            "title": title,
            "type": "Manga",
            "rating_votes": votes,
            "bayesian_rating": rating,
        },
        "hit_title": title if hit_title is None else hit_title,
    }


def _titles(items):
    return [item["record"]["title"] for item in items]


# ผลจริงของ {"search": "one piece", "type": ["Manga"]} เรียงตามที่ API ส่งมา
ONE_PIECE = [
    _item("One Piece", series_id=55099564912, votes=5352, rating=8.89),
    _item("Odekake One Piece", series_id=34866131632),
    _item("One Piece Party", series_id=49512032547, votes=26, rating=6.32),
    _item("Koisuru One Piece", series_id=77556276839, votes=5, rating=6.21),
    _item("One Piece Gakuen", series_id=15967490973, votes=9, rating=6.14),
    # สองตัวนี้โผล่มาจริงตอนค้น "one pece" - ติดมาเพราะคำว่า one คำเดียว
    _item("One One Onegai Onee-san", series_id=1001),
    _item("Fuufu no Uragao", hit_title="One & One", series_id=1002),
]

# ผลจริงของ {"search": "demon slayer", "type": ["Manga"]}
DEMON_SLAYER = [
    _item("Kimetsu no Yaiba", hit_title="Demon Slayer", series_id=2001, votes=4000, rating=8.5),
    _item("Ayashiya", hit_title="Ayashiya the Demon Slayer", series_id=2002),
    _item("Momoiro Toukiden Momotarou-kun", hit_title="Pink Demon Slayer Momotarou", series_id=2003),
    _item("Mukurozumi no Volte", hit_title="Slayer Volte", series_id=2004),
]


class NormalizeTests(unittest.TestCase):

    def test_ignores_case_and_punctuation(self):
        self.assertEqual(normalize("One & One"), "one one")
        self.assertEqual(normalize("Boruto - Naruto the Movie"), "boruto naruto the movie")
        self.assertEqual(normalize("  ONE   PIECE  "), "one piece")

    def test_handles_missing_text(self):
        self.assertEqual(normalize(None), "")
        self.assertEqual(normalize(""), "")


class ScoreTests(unittest.TestCase):

    def test_exact_title_scores_highest(self):
        self.assertEqual(score_item("one piece", _item("One Piece")), 1.0)

    def test_uses_hit_title_when_main_title_does_not_match(self):
        # ชื่อหลักเป็นภาษาญี่ปุ่น แต่ผู้ใช้พิมพ์ชื่ออังกฤษที่อยู่ในชื่อรอง
        item = _item("Kimetsu no Yaiba", hit_title="Demon Slayer")
        self.assertEqual(score_item("demon slayer", item), 1.0)

    def test_single_shared_word_falls_below_floor(self):
        # 'One & One' มีคำว่า one เหมือนกัน แต่ไม่มี piece เลย
        item = _item("Fuufu no Uragao", hit_title="One & One")
        self.assertLess(score_item("one piece", item), MATCH_FLOOR)

    def test_typo_still_passes_floor(self):
        self.assertGreaterEqual(score_item("one pece", _item("One Piece")), MATCH_FLOOR)


class RankTests(unittest.TestCase):

    def test_exact_title_stays_first(self):
        ranked = rank("one piece", ONE_PIECE, limit=10)
        self.assertEqual(_titles(ranked)[0], "One Piece")

    def test_exact_title_promoted_when_api_puts_it_last(self):
        # ลำดับสังเคราะห์ - กลับหัวของจริงเพื่อพิสูจน์ว่าเราจัดอันดับเองจริง
        ranked = rank("one piece", list(reversed(ONE_PIECE)), limit=10)
        self.assertEqual(_titles(ranked)[0], "One Piece")

    def test_drops_results_that_only_share_one_word(self):
        titles = _titles(rank("one piece", ONE_PIECE, limit=10))
        self.assertNotIn("Fuufu no Uragao", titles)
        self.assertNotIn("One One Onegai Onee-san", titles)

    def test_alternate_title_hit_ranks_first(self):
        ranked = rank("demon slayer", DEMON_SLAYER, limit=10)
        self.assertEqual(_titles(ranked)[0], "Kimetsu no Yaiba")

    def test_drops_partial_alternate_title_match(self):
        # 'Slayer Volte' มีแค่คำว่า slayer ไม่มี demon
        titles = _titles(rank("demon slayer", DEMON_SLAYER, limit=10))
        self.assertNotIn("Mukurozumi no Volte", titles)

    def test_typo_query_keeps_the_right_series(self):
        ranked = rank("one pece", ONE_PIECE, limit=10)
        self.assertEqual(_titles(ranked)[0], "One Piece")

    def test_falls_back_to_api_order_when_nothing_passes_floor(self):
        # คำค้นที่ไม่ใกล้อะไรเลย ต้องไม่คืนลิสต์ว่าง เพราะ API เรียง relevance มาแล้ว
        ranked = rank("zzzqqxyw", ONE_PIECE, limit=3)
        self.assertEqual(len(ranked), 3)
        self.assertEqual(_titles(ranked), _titles(ONE_PIECE[:3]))

    def test_limit_is_respected(self):
        self.assertEqual(len(rank("one piece", ONE_PIECE, limit=2)), 2)

    def test_popularity_breaks_ties(self):
        # คะแนนชื่อเท่ากันทั้งคู่ (ขึ้นต้นด้วยคำค้น) ตัวที่คนโหวตเยอะกว่าควรมาก่อน
        quiet = _item("Dungeon Nursery", series_id=3001, votes=5, rating=6.0)
        popular = _item("Dungeon Meshi", series_id=3002, votes=3000, rating=8.7)
        ranked = rank("dungeon", [quiet, popular], limit=10)
        self.assertEqual(_titles(ranked), ["Dungeon Meshi", "Dungeon Nursery"])

    def test_empty_input_gives_empty_output(self):
        self.assertEqual(rank("one piece", [], limit=10), [])


if __name__ == "__main__":
    unittest.main()
