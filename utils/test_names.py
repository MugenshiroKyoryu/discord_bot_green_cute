#!/usr/bin/env python3
"""เทสต์การจัดชื่อรองก่อนแสดงใน embed

ใช้ unittest ของ stdlib ตามที่โปรเจกต์ทำอยู่ ไม่เพิ่ม dependency
ชื่อตัวอย่างถอดมาจาก associated_names จริงของ 'Akame ga Kiru!' ซึ่งเป็นเคส
ที่แสดงผลพังจริง - ชื่อเปอร์เซียกับฮีบรูดึงบรรทัดตัวเองไปชิดขวา

    python -m unittest discover -s utils -p "test_*.py" -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils._names import (  # noqa: E402
    FIELD_LIMIT,
    MAX_NAMES,
    clean_names,
    format_alt_names,
)

LRM = "‎"
LRI = "⁦"
PDI = "⁩"

# ตามลำดับที่ MangaUpdates ส่งมาจริง - เปอร์เซียมาก่อนชื่อละตินทั้งหมด
AKAME = [
    "آکامه گا کیل!",
    "Akame ga KILL!",
    "Akame Kills!",
    "Akame Slashes!",
    "Убийца Акаме!",
    "אקאמה גה קיל",
    "อาคาเมะสวยประหาร",
    "アカメが斬る！",
    "아카메가 벤다!",
]


def _lines(text: str) -> list[str]:
    return text.split("\n")


def _bare(line: str) -> str:
    """ถอดอักขระคุมทิศทางออก เหลือแต่ตัวชื่อ"""
    return line.replace(LRM, "").replace(LRI, "").replace(PDI, "")


class CleanNamesTests(unittest.TestCase):

    def test_blank_entries_disappear(self):
        # ชื่อว่างจากต้นทางกลายเป็นบรรทัดเปล่ากลางรายการถ้าไม่กรองทิ้ง
        self.assertEqual(clean_names(["One Piece", "", "   ", None]), ["One Piece"])

    def test_same_name_in_a_different_case_is_a_duplicate(self):
        self.assertEqual(
            clean_names(["Akame ga KILL!", "Akame ga Kill!"]),
            ["Akame ga KILL!"],
        )

    def test_names_that_differ_by_punctuation_are_kept_apart(self):
        # ต้นทางแยกสองรายการนี้ไว้จริง ไม่ใช่ข้อมูลซ้ำ
        self.assertEqual(
            clean_names(["아카메가 벤다!", "아카메가 벤다!!"]),
            ["아카메가 벤다!", "아카메가 벤다!!"],
        )

    def test_newlines_inside_a_name_are_flattened(self):
        # ขึ้นบรรทัดใหม่กลางชื่อทำให้เค้าโครง 1 บรรทัด 1 ชื่อ เพี้ยน
        self.assertEqual(clean_names(["Red Eyes\nSword"]), ["Red Eyes Sword"])

    def test_bidi_controls_from_the_source_are_stripped(self):
        # ปล่อยไว้จะไปทับอักขระคุมทิศทางที่เราใส่เอง
        self.assertEqual(clean_names([f"{LRI}Akame{PDI}"]), ["Akame"])

    def test_none_gives_an_empty_list(self):
        self.assertEqual(clean_names(None), [])


class DirectionTests(unittest.TestCase):

    def test_every_line_starts_with_an_ltr_mark(self):
        # LRM เป็นอักขระ strong ตัวแรกของบรรทัด ทิศย่อหน้าจึงเป็น LTR ทุกบรรทัด
        for line in _lines(format_alt_names(AKAME)):
            self.assertTrue(line.startswith(LRM), line)

    def test_rtl_names_are_isolated(self):
        lines = _lines(format_alt_names(["آکامه گا کیل!", "אקאמה גה קיל"]))
        for line in lines:
            self.assertEqual(line.count(LRI), 1)
            self.assertEqual(line.count(PDI), 1)
            self.assertLess(line.index(LRI), line.index(PDI))

    def test_the_name_itself_is_untouched(self):
        # คุมแค่ทิศทาง ไม่แก้ตัวอักษรในชื่อ
        self.assertEqual(_bare(format_alt_names(["آکامه گا کیل!"])), "آکامه گا کیل!")


class OrderTests(unittest.TestCase):

    def test_readable_scripts_come_before_right_to_left_ones(self):
        names = [_bare(line) for line in _lines(format_alt_names(AKAME))]
        self.assertLess(names.index("Akame ga KILL!"), names.index("آکامه گا کیل!"))
        self.assertLess(names.index("อาคาเมะสวยประหาร"), names.index("אקאמה גה קיל"))

    def test_script_groups_are_ordered_latin_cjk_cyrillic_rtl(self):
        names = [_bare(line) for line in _lines(format_alt_names(AKAME))]
        self.assertEqual(
            names,
            [
                "Akame ga KILL!",
                "Akame Kills!",
                "Akame Slashes!",
                "อาคาเมะสวยประหาร",
                "アカメが斬る！",
                "아카메가 벤다!",
                "Убийца Акаме!",
                "آکامه گا کیل!",
                "אקאמה גה קיל",
            ],
        )

    def test_order_inside_a_group_follows_the_source(self):
        names = [_bare(line) for line in _lines(format_alt_names(AKAME))]
        self.assertLess(names.index("Akame Kills!"), names.index("Akame Slashes!"))

    def test_a_title_starting_with_a_digit_counts_as_latin(self):
        names = [_bare(line) for line in _lines(format_alt_names(["آکامه", "20th Century Boys"]))]
        self.assertEqual(names[0], "20th Century Boys")


class LimitTests(unittest.TestCase):

    def test_long_lists_are_capped_and_the_rest_is_counted(self):
        text = format_alt_names([f"Name {i}" for i in range(MAX_NAMES + 4)])
        lines = _lines(text)
        self.assertEqual(len(lines), MAX_NAMES + 1)
        self.assertEqual(lines[-1], "… และอีก 4 ชื่อ")

    def test_a_short_list_has_no_summary_line(self):
        self.assertNotIn("และอีก", format_alt_names(["One Piece", "Wan Pisu"]))

    def test_the_field_limit_is_never_exceeded(self):
        text = format_alt_names(["ชื่อยาวมากจนเกินลิมิต" * 8 for _ in range(MAX_NAMES)])
        self.assertLessEqual(len(text), FIELD_LIMIT)

    def test_dropped_lines_are_added_to_the_hidden_count(self):
        # ตัดเพราะยาวเกิน ไม่ใช่เพราะเกินจำนวน - ยอดที่ซ่อนต้องนับรวมด้วย
        text = format_alt_names([f"{i}" + "x" * 300 for i in range(6)])
        self.assertLessEqual(len(text), FIELD_LIMIT)
        self.assertEqual(_lines(text)[-1], "… และอีก 3 ชื่อ")

    def test_truncation_never_splits_a_control_character_pair(self):
        text = format_alt_names([f"{i}" + "x" * 400 for i in range(9)])
        self.assertEqual(text.count(LRI), text.count(PDI))

    def test_a_single_name_longer_than_the_limit_is_shortened(self):
        text = format_alt_names(["ก" * (FIELD_LIMIT + 50)])
        self.assertLessEqual(len(text), FIELD_LIMIT)
        self.assertEqual(text.count(LRI), text.count(PDI))
        self.assertTrue(_bare(text).endswith("…"))


class EmptyResultTests(unittest.TestCase):

    def test_no_names_gives_an_empty_string(self):
        # ผู้เรียกใช้ค่านี้ตัดสินใจซ่อนฟิลด์
        self.assertEqual(format_alt_names([]), "")

    def test_names_that_are_all_blank_give_an_empty_string(self):
        self.assertEqual(format_alt_names(["", "  "]), "")

    def test_none_gives_an_empty_string(self):
        self.assertEqual(format_alt_names(None), "")


if __name__ == "__main__":
    unittest.main()
