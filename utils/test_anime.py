#!/usr/bin/env python3
"""เทสต์การจัดตอนเริ่ม/จบของฉบับอนิเมะก่อนแสดงใน embed

ใช้ unittest ของ stdlib ตามที่โปรเจกต์ทำอยู่ ไม่เพิ่ม dependency
ข้อมูลตัวอย่างถอดมาจาก anime.start/anime.end จริงของ 'Kakkou no Iinazuke'
กับ 'Gaikotsu Kishi-sama' ซึ่งเป็นสองเคสที่อ่านไม่ออกจริง - ต้นทางจัดตามแกน
เริ่ม/จบ ซีซั่นจึงปนกันอยู่คนละบรรทัด และซีซั่นที่ยังไม่จบทำให้สองบรรทัด
มีจำนวนรายการไม่เท่ากันจนจับคู่ด้วยตาไม่ได้

    python -m unittest discover -s utils -p "test_*.py" -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils._anime import (  # noqa: E402
    FIELD_LIMIT,
    format_anime_chapters,
)

# ค่าจริงจาก MangaUpdates - อนิเมะสองซีซั่นที่จบครบทั้งคู่
KAKKOU_START = "Vol 1, Chap 0 (S1) / Vol 8, Chap 61 (S2)"
KAKKOU_END = "Vol 7, Chap 60 (S1) / Vol 13, Chap 112 (S2)"

# ค่าจริงจาก MangaUpdates - S2 ยังไม่จบ ฝั่ง end จึงมีแค่ S1
GAIKOTSU_START = "Vol 1, Chap 1 (S1) / Vol 5, Chap 21 (S2)"
GAIKOTSU_END = "Vol 4, Chap 20 (S1)"

# ค่าจริงจาก MangaUpdates - ตัวคั่นไม่มีช่องว่างตามหลัง ('(S1) /Vol 5')
MAGILUMIERE_START = "Vol 1, Chap 1 (S1) /Vol 5, Chap 34 (S2)"
MAGILUMIERE_END = "Vol 5, Chap 33 (S1)"


def _lines(text: str) -> list[str]:
    return text.split("\n")


class SeasonPairingTests(unittest.TestCase):

    def test_each_season_gets_its_own_start_and_end_on_one_line(self):
        # หัวใจของการแก้ - พลิกแกนจาก "เริ่มทั้งหมด / จบทั้งหมด" เป็นรายซีซั่น
        self.assertEqual(
            _lines(format_anime_chapters(KAKKOU_START, KAKKOU_END)),
            [
                "S1 · Vol 1, Chap 0 → Vol 7, Chap 60",
                "S2 · Vol 8, Chap 61 → Vol 13, Chap 112",
            ],
        )

    def test_a_season_that_has_not_finished_says_so(self):
        # S2 ไม่มีอยู่ในฝั่ง end เลย ห้ามเงียบหรือจับคู่มั่ว
        self.assertEqual(
            _lines(format_anime_chapters(GAIKOTSU_START, GAIKOTSU_END)),
            [
                "S1 · Vol 1, Chap 1 → Vol 4, Chap 20",
                "S2 · Vol 5, Chap 21 → ยังไม่จบ",
            ],
        )

    def test_seasons_keep_the_order_the_source_gave(self):
        text = format_anime_chapters(
            "Vol 8, Chap 61 (S2) / Vol 1, Chap 0 (S1)",
            KAKKOU_END,
        )
        self.assertTrue(_lines(text)[0].startswith("S2 · "))

    def test_a_season_missing_from_the_start_side_still_shows_up(self):
        text = format_anime_chapters("Vol 1, Chap 1 (S1)", GAIKOTSU_END + " / Vol 9, Chap 44 (S2)")
        self.assertEqual(
            _lines(text)[1],
            "S2 · ไม่ระบุ → Vol 9, Chap 44",
        )

    def test_labels_that_are_not_season_numbers_are_kept(self):
        # ต้นทางติดป้ายอย่าง (OVA) (Movie) มาด้วย ทิ้งไปแล้วเข้าใจผิดว่าเป็นซีซั่นหลัก
        self.assertEqual(
            format_anime_chapters("Vol 2, Chap 10 (OVA)", "Vol 2, Chap 12 (OVA)"),
            "OVA · Vol 2, Chap 10 → Vol 2, Chap 12",
        )


class SingleSeasonTests(unittest.TestCase):

    def test_no_label_means_no_prefix(self):
        # อนิเมะซีซั่นเดียวไม่ติดป้ายมา อย่าไปแต่ง S1 ให้เอง
        self.assertEqual(
            format_anime_chapters("Vol 1, Chap 1", "Vol 12, Chap 95"),
            "Vol 1, Chap 1 → Vol 12, Chap 95",
        )

    def test_only_a_start_is_known(self):
        self.assertEqual(
            format_anime_chapters("Vol 1, Chap 1", "Unknown"),
            "Vol 1, Chap 1 → ยังไม่จบ",
        )

    def test_only_an_end_is_known(self):
        self.assertEqual(
            format_anime_chapters("Unknown", "Vol 12, Chap 95"),
            "ไม่ระบุ → Vol 12, Chap 95",
        )


class MessySourceTests(unittest.TestCase):

    def test_newlines_from_the_source_do_not_leave_a_blank_line(self):
        # บรรทัดว่างกลางฟิลด์ที่ผู้ใช้เห็นจริงมาจาก \n ที่ติดมากับค่า
        text = format_anime_chapters(f"{GAIKOTSU_START}\n", f"\n{GAIKOTSU_END}")
        self.assertNotIn("\n\n", text)
        self.assertEqual(len(_lines(text)), 2)

    def test_a_slash_inside_a_chapter_number_is_not_a_separator(self):
        # เลขตอนไม่มีช่องว่างคร่อม "/" และไม่มีวงเล็บปิดนำหน้า จึงไม่ใช่ตัวคั่น
        self.assertEqual(
            format_anime_chapters("Vol 1, Chap 1/2", "Vol 3, Chap 20"),
            "Vol 1, Chap 1/2 → Vol 3, Chap 20",
        )

    def test_a_separator_without_a_trailing_space_still_splits(self):
        # ต้นทางเขียน '(S1) /Vol 5' ติดกัน ยึด " / " ตายตัวจะได้รายการเดียว
        # แล้วป้าย (S2) ท้ายสุดจะกลืน S1 ไปทั้งดุ้น จนสองบรรทัดสลับหัวท้ายกัน
        self.assertEqual(
            _lines(format_anime_chapters(MAGILUMIERE_START, MAGILUMIERE_END)),
            [
                "S1 · Vol 1, Chap 1 → Vol 5, Chap 33",
                "S2 · Vol 5, Chap 34 → ยังไม่จบ",
            ],
        )

    def test_a_separator_with_no_spaces_at_all_splits_after_a_label(self):
        # ไม่มีช่องว่างสักฝั่ง แต่วงเล็บปิดของป้ายบอกได้ว่าจบรายการแล้ว
        self.assertEqual(
            _lines(format_anime_chapters(
                "Vol 1, Chap 1 (S1)/Vol 5, Chap 34 (S2)",
                "Vol 5, Chap 33 (S1)",
            )),
            [
                "S1 · Vol 1, Chap 1 → Vol 5, Chap 33",
                "S2 · Vol 5, Chap 34 → ยังไม่จบ",
            ],
        )

    def test_uneven_unlabelled_lists_pair_up_by_position(self):
        # ไม่มีป้ายให้จับคู่ ก็เรียงตามลำดับที่ได้มา ดีกว่าทิ้งข้อมูล
        self.assertEqual(
            _lines(format_anime_chapters("Vol 1, Chap 1 / Vol 5, Chap 21", "Vol 4, Chap 20")),
            [
                "Vol 1, Chap 1 → Vol 4, Chap 20",
                "Vol 5, Chap 21 → ยังไม่จบ",
            ],
        )

    def test_a_label_with_nothing_in_front_of_it_is_dropped(self):
        self.assertEqual(format_anime_chapters("(S1)", "Unknown"), "")


class EmptyResultTests(unittest.TestCase):

    def test_unknown_on_both_sides_gives_an_empty_string(self):
        # ผู้เรียกใช้ค่านี้ตัดสินใจซ่อนฟิลด์ - เรื่องส่วนใหญ่ไม่เคยมีอนิเมะ
        self.assertEqual(format_anime_chapters("Unknown", "Unknown"), "")

    def test_none_gives_an_empty_string(self):
        self.assertEqual(format_anime_chapters(None, None), "")

    def test_blank_strings_give_an_empty_string(self):
        self.assertEqual(format_anime_chapters("", "   "), "")

    def test_non_strings_give_an_empty_string(self):
        self.assertEqual(format_anime_chapters(0, []), "")


class LimitTests(unittest.TestCase):

    def test_the_field_limit_is_never_exceeded(self):
        seasons = " / ".join(f"Vol {i}, Chap {i * 10} (S{i})" for i in range(1, 60))
        text = format_anime_chapters(seasons, seasons)
        self.assertLessEqual(len(text), FIELD_LIMIT)

    def test_dropped_seasons_are_counted_in_a_summary_line(self):
        seasons = " / ".join(f"Vol {i}, Chap {i * 10} (S{i})" for i in range(1, 60))
        self.assertTrue(_lines(format_anime_chapters(seasons, seasons))[-1].startswith("… และอีก "))

    def test_a_single_line_longer_than_the_limit_is_shortened(self):
        text = format_anime_chapters("Vol 1, " + "x" * (FIELD_LIMIT + 50), "Unknown")
        self.assertLessEqual(len(text), FIELD_LIMIT)
        self.assertTrue(text.endswith("…"))


if __name__ == "__main__":
    unittest.main()
