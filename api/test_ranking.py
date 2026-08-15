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

from api._ranking import (  # noqa: E402
    MATCH_FLOOR,
    detail_score,
    normalize,
    rank,
    rerank_details,
    score_item,
)


def _item(title, hit_title=None, series_id=1, votes=0, rating=None, series_type="Manga"):
    """ผลลัพธ์ 1 รายการตามรูปของ SeriesSearchResponseV1.results"""
    return {
        "record": {
            "series_id": series_id,
            "title": title,
            "type": series_type,
            "rating_votes": votes,
            "bayesian_rating": rating,
        },
        "hit_title": title if hit_title is None else hit_title,
    }


def _detail(title, associated=None, series_id=1):
    """รายละเอียด 1 เรื่องตามรูปที่ fetch_series_detail คืนมา - เอาเฉพาะฟิลด์ที่ใช้จัดอันดับ"""
    return {
        "series_id": series_id,
        "title": title,
        "associated_names": list(associated or []),
    }


def _titles(items):
    return [item["record"]["title"] for item in items]


def _detail_titles(details):
    return [detail["title"] for detail in details]


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

# ผลจริงของการค้นด้วยชื่อเต็มของฉบับมังงะ ฉบับนิยายมาที่อันดับ 2 ตั้งแต่ API แล้ว
# แต่เดิมได้แค่ 0.32 เลยโดนตัดทิ้ง เหลือผลเดียวทั้งที่เรื่องนี้มีนิยายอยู่
KONJIKI_QUERY = "Konjiki no Moji Tsukai - Yuusha Yonin ni Makikomareta Unique Cheat"

KONJIKI = [
    _item(
        "Konjiki no Word Master: Yuusha Yonin ni Makikomareta Unique Cheat",
        hit_title="Konjiki no Moji Tsukai - Yuusha Yonin ni Makikomareta Unique Cheat",
        series_id=67937814952,
    ),
    _item("Konjiki no Moji Tsukai (Novel)", series_id=17505874636, series_type="Novel"),
    _item("Nioh: Konjiki no Samurai", series_id=35659308911),
    _item("Konjiki no Gash!! 2", series_id=19709504463),
    _item("Moji Moji Koi Shiteru", hit_title="Moji Moji Koishiteru", series_id=56840476693),
    _item("Konjiki no Gash!!", series_id=62053723305),
]

# ผลจริงของ {"search": "demon slayer", "type": ["Manga"]}
DEMON_SLAYER = [
    _item("Kimetsu no Yaiba", hit_title="Demon Slayer", series_id=2001, votes=4000, rating=8.5),
    _item("Ayashiya", hit_title="Ayashiya the Demon Slayer", series_id=2002),
    _item("Momoiro Toukiden Momotarou-kun", hit_title="Pink Demon Slayer Momotarou", series_id=2003),
    _item("Mukurozumi no Volte", hit_title="Slayer Volte", series_id=2004),
]


# ผลจริงของ {"search": "akame ga kill", "type": ["Manga"]} เรียงตามที่ API ส่งมา
# ยกเว้นตัวสุดท้าย hit_title เท่ากับชื่อหลักทุกตัว - API ไม่ส่งชื่อรองที่ทำให้แมตช์กลับมาด้วย
# ผู้ใช้พิมพ์ชื่ออังกฤษ 'kill' แต่ชื่อหลักเป็นโรมาจิ 'Kiru' รอบแรกจึงมองไม่เห็นว่าตรง
AKAME = [
    _item("Akame ga Kiru! Zero", series_id=61228207477, votes=111, rating=6.92),
    _item("Akame ga Kiru! 1.5", series_id=32641502508, votes=19, rating=6.31),
    _item("Akame ga Kiru!", series_id=54773004994, votes=1258, rating=7.86),
    _item("Akame", series_id=31929938980, votes=21, rating=6.9),
    _item("Akame no Daiji", series_id=59020426045, votes=1, rating=6.23),
    _item("Akame No Tatari", series_id=17509160105),
    _item("Kill la Kill", series_id=8928353448, votes=45, rating=5.79),
    _item("Kill Time Seiheki Series Dochi ga Eroi!?", series_id=61608895239, votes=1, rating=6.2),
    _item("Dolly Kill Kill", series_id=37451551144, votes=123, rating=6.78),
    _item(
        "Zansatsu Hantou Akamemura",
        hit_title="Zansatsu Hantou Akame Mura",
        series_id=40370907977, votes=1, rating=6.3,
    ),
]

# associated ของ GET /series/{id} ของ 10 เรื่องข้างบน เรียงตามลำดับเดียวกัน
# ชื่อรองภาษาอื่นเก็บไว้ด้วย จะได้พิสูจน์ว่ามันไม่ดันคะแนนมั่ว
AKAME_DETAILS = [
    _detail(
        "Akame ga Kiru! Zero",
        [
            "Akame ga Kill! Zero",
            "Akame ga Kiru! Rei",
            "Убийца Акаме! Начало",
            "อาคาเมะ สวยประหาร Zero (SIC)",
            "アカメが斬る! 零",
        ],
        series_id=61228207477,
    ),
    _detail(
        "Akame ga Kiru! 1.5",
        ["Akame ga Kill! 1.5", "アカメが斬る！ 1.5"],
        series_id=32641502508,
    ),
    _detail(
        "Akame ga Kiru!",
        [
            "!آکامه گا کیل",
            "Akame ga KILL!",
            "Akame Kills!",
            "Akame Slashes!",
            "Akame, Keser!",
            "Red Eyes Sword – Akame ga Kill !",
            "Red-Eye Kills!",
            "Убивця Акаме!",
            "Убийца Акаме!",
            "אקאמה גה קיל",
            "อาคาเมะสวยประหาร",
            "アカメが斬る！",
            "아카메가 벤다!",
            "아카메가 벤다!!",
        ],
        series_id=54773004994,
    ),
    _detail(
        "Akame",
        ["Akame - The Red Eyes", "Akame The Red Eyes", "赤目"],
        series_id=31929938980,
    ),
    _detail("Akame no Daiji", ["赤目の大事"], series_id=59020426045),
    _detail("Akame No Tatari", ["赤目のたたり"], series_id=17509160105),
    _detail("Kill la Kill", ["キルラキル"], series_id=8928353448),
    _detail(
        "Kill Time Seiheki Series Dochi ga Eroi!?",
        ["キルタイム性癖シリーズ どっちがエロい!？"],
        series_id=61608895239,
    ),
    _detail(
        "Dolly Kill Kill",
        ["Dolly♥Kill Kill", "ตุ๊กตาพันธุ์โหด", "ドリィ キルキル"],
        series_id=37451551144,
    ),
    _detail(
        "Zansatsu Hantou Akamemura",
        ["Zansatsu Hantou Akame Mura", "Zansatsu Hantou Akame-mura", "惨殺半島 赤目村"],
        series_id=40370907977,
    ),
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

    def test_shorter_title_contained_in_query_passes_floor(self):
        # ฉบับนิยายใช้ชื่อสั้นกว่าฉบับมังงะที่ผู้ใช้พิมพ์มา ต้องไม่ถูกตัดเพราะคำค้นยาว
        item = _item("Konjiki no Moji Tsukai (Novel)", series_type="Novel")
        self.assertGreaterEqual(score_item(KONJIKI_QUERY, item), MATCH_FLOOR)

    def test_trailing_marker_is_ignored_when_comparing(self):
        # '(Novel)' เป็นตัวกำกับของเว็บ ไม่ใช่ส่วนหนึ่งของชื่อเรื่อง
        item = _item("Konjiki no Moji Tsukai (Novel)", series_type="Novel")
        self.assertEqual(score_item("konjiki no moji tsukai", item), 1.0)

    def test_single_word_title_is_not_promoted_by_containment(self):
        # ถ้าไม่มีเกณฑ์จำนวนคำ ชื่อคำเดียวจะลอยขึ้นมาทุกคำค้นที่มีคำนั้น
        self.assertLess(score_item("one piece", _item("Piece")), MATCH_FLOOR)


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

    def test_novel_edition_survives_a_long_manga_query(self):
        # จุดอ่อนที่รายงานเข้ามา - เรื่องนี้มีนิยายแต่ผลค้นหาเจอแค่มังงะ
        titles = _titles(rank(KONJIKI_QUERY, KONJIKI, limit=10))
        self.assertIn("Konjiki no Moji Tsukai (Novel)", titles)

    def test_manga_edition_still_ranks_above_the_novel(self):
        titles = _titles(rank(KONJIKI_QUERY, KONJIKI, limit=10))
        self.assertEqual(
            titles[:2],
            [
                "Konjiki no Word Master: Yuusha Yonin ni Makikomareta Unique Cheat",
                "Konjiki no Moji Tsukai (Novel)",
            ],
        )

    def test_unrelated_titles_sharing_one_word_still_dropped(self):
        # ต้องไม่แลกมาด้วยการปล่อยเรื่องที่แค่มีคำว่า konjiki หรือ moji เข้ามา
        titles = _titles(rank(KONJIKI_QUERY, KONJIKI, limit=10))
        self.assertNotIn("Konjiki no Gash!!", titles)
        self.assertNotIn("Konjiki no Gash!! 2", titles)
        self.assertNotIn("Nioh: Konjiki no Samurai", titles)
        self.assertNotIn("Moji Moji Koi Shiteru", titles)


class AkameStageOneTests(unittest.TestCase):
    """ล็อกอาการของบั๊กไว้ - รอบแรกช่วยเคสชื่อโรมาจิ vs ชื่ออังกฤษไม่ได้"""

    def test_every_candidate_falls_below_the_floor(self):
        # 'kiru' กับ 'kill' ใกล้กันแค่ 0.5 ไม่ถึงเกณฑ์ของ token ทุกเรื่องเลยตกพร้อมกัน
        for item in AKAME:
            with self.subTest(title=item["record"]["title"]):
                self.assertLess(score_item("akame ga kill", item), MATCH_FLOOR)

    def test_api_order_puts_the_prequel_before_the_main_series(self):
        # ไม่มีใครผ่านเกณฑ์ รอบแรกจึงคืนลำดับดิบของ API ซึ่งเอาภาคก่อนหน้ามาก่อน
        titles = _titles(rank("akame ga kill", AKAME, limit=10))
        self.assertEqual(titles[0], "Akame ga Kiru! Zero")
        self.assertEqual(titles.index("Akame ga Kiru!"), 2)

    def test_api_order_also_lets_unrelated_titles_through(self):
        titles = _titles(rank("akame ga kill", AKAME, limit=10))
        self.assertIn("Kill la Kill", titles)
        self.assertIn("Dolly Kill Kill", titles)


class DetailScoreTests(unittest.TestCase):

    def test_associated_name_lifts_a_romanized_title(self):
        # ชื่อหลัก 'Akame ga Kiru!' ไม่ตรง แต่ชื่อรอง 'Akame ga KILL!' ตรงเป๊ะ
        detail = _detail("Akame ga Kiru!", ["Akame ga KILL!"])
        self.assertEqual(detail_score("akame ga kill", detail), 1.0)

    def test_title_alone_is_used_when_there_are_no_associated_names(self):
        self.assertEqual(detail_score("one piece", _detail("One Piece")), 1.0)

    def test_missing_associated_names_key_does_not_break(self):
        self.assertEqual(detail_score("one piece", {"title": "One Piece"}), 1.0)

    def test_non_latin_names_do_not_inflate_the_score(self):
        detail = _detail("Kill la Kill", ["キルラキル"])
        self.assertLess(detail_score("akame ga kill", detail), MATCH_FLOOR)


class RerankDetailsTests(unittest.TestCase):

    def test_main_series_beats_the_prequel(self):
        # จุดที่รายงานเข้ามา - ผู้ใช้หาภาคหลัก แต่ได้ภาคก่อนหน้าเป็นอันดับ 1
        ranked = rerank_details("akame ga kill", AKAME_DETAILS)
        self.assertEqual(ranked[0]["title"], "Akame ga Kiru!")

    def test_keeps_the_side_stories_below_the_main_series(self):
        # ภาคแยกยังอยู่ ผู้ใช้กดดูต่อได้ แค่ต้องไม่มาก่อนภาคหลัก
        self.assertEqual(
            _detail_titles(rerank_details("akame ga kill", AKAME_DETAILS)),
            ["Akame ga Kiru!", "Akame ga Kiru! Zero", "Akame ga Kiru! 1.5"],
        )

    def test_drops_titles_that_only_share_one_word(self):
        titles = _detail_titles(rerank_details("akame ga kill", AKAME_DETAILS))
        for junk in (
            "Akame",
            "Akame no Daiji",
            "Akame No Tatari",
            "Kill la Kill",
            "Kill Time Seiheki Series Dochi ga Eroi!?",
            "Dolly Kill Kill",
            "Zansatsu Hantou Akamemura",
        ):
            with self.subTest(title=junk):
                self.assertNotIn(junk, titles)

    def test_ties_keep_the_order_they_came_in_with(self):
        # ทั้งคู่ได้ 0.9 เท่ากัน ต้องคงลำดับจากรอบแรกที่ตัดสินด้วยความนิยมมาแล้ว
        zero = _detail("Akame ga Kiru! Zero", ["Akame ga Kill! Zero"], series_id=1)
        one_five = _detail("Akame ga Kiru! 1.5", ["Akame ga Kill! 1.5"], series_id=2)
        self.assertEqual(
            _detail_titles(rerank_details("akame ga kill", [one_five, zero])),
            ["Akame ga Kiru! 1.5", "Akame ga Kiru! Zero"],
        )

    def test_falls_back_to_the_given_order_when_nothing_passes(self):
        # เหตุผลเดียวกับ rank() - คืนลำดับเดิมดีกว่าคืนลิสต์ว่างให้ผู้ใช้
        details = AKAME_DETAILS[6:9]
        self.assertEqual(rerank_details("akame ga kill", details), details)

    def test_empty_input_gives_empty_output(self):
        self.assertEqual(rerank_details("akame ga kill", []), [])

    def test_does_not_mutate_the_list_it_was_given(self):
        details = list(AKAME_DETAILS)
        rerank_details("akame ga kill", details)
        self.assertEqual(details, AKAME_DETAILS)


if __name__ == "__main__":
    unittest.main()
