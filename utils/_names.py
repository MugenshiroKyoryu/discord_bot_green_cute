"""จัดชื่อรองให้แสดงใน embed ได้โดยไม่พังการจัดวาง

MangaUpdates ส่ง associated_names มาคละภาษา รวมถึงภาษาที่เขียนขวาไปซ้าย
(อาหรับ เปอร์เซีย ฮีบรู) ถ้าเอามาต่อด้วย "\\n" ดิบ ๆ Discord ซึ่งวางอยู่บน
Chromium จะตัดสินทิศทางของย่อหน้าทีละบรรทัดตาม Unicode Bidirectional Algorithm
บรรทัดที่ตัวอักษรตัวแรกเป็น RTL จึงกลายเป็นย่อหน้า RTL ทั้งบรรทัด - ชิดขวา
เหลือช่องว่างยาวทางซ้าย และเครื่องหมายท้ายชื่อเด้งไปอยู่หน้าสุด
('Akame ga Kiru!' ฉบับเปอร์เซียแสดงเป็น '!آکامه گا کیل')

โมดูลนี้จึงบังคับทิศทางของทุกบรรทัดให้เป็น LTR แล้วห่อชื่อไว้ใน isolate
เพื่อไม่ให้สคริปต์ข้างในไปกวนบรรทัดอื่น

แยกจาก series_view.py เพราะเป็นฟังก์ชันล้วน ไม่แตะ discord จึงเทสได้ตรง ๆ
"""

from __future__ import annotations

import re

# ลิมิตของ EmbedFieldValue ตามสเปก Discord - เกินนี้ API ตอบ 400
FIELD_LIMIT = 1024

# เกินจำนวนนี้ผู้ใช้ก็ไม่ได้อ่านแล้ว และบรรทัดภาษาที่ต้องใช้ฟอนต์สำรอง
# ยิ่งเยอะยิ่งดันความสูงของ embed ทั้งก้อน
MAX_NAMES = 15

# U+200E LRM เป็นอักขระ strong ฝั่ง LTR วางหน้าบรรทัดแล้วกฎ P2 ของ UBA
# จะได้ทิศย่อหน้าเป็น LTR ทันที ทุกบรรทัดจึงชิดซ้ายเท่ากันหมด
_LRM = "‎"

# U+2066 LRI / U+2069 PDI คร่อมชื่อไว้เป็นก้อนเดียวทิศ LTR ตัวอักษรอาหรับ
# ข้างในยังเรียงขวาไปซ้ายตามปกติของภาษา แต่เครื่องหมายท้ายชื่อไม่หลุดไปหัวบรรทัด
# และชื่อก้อนนี้กวนบรรทัดอื่นไม่ได้เพราะถูก isolate ไว้
_LRI = "⁦"
_PDI = "⁩"

# ถ้าข้อมูลต้นทางมีอักขระคุมทิศทางติดมาเอง มันจะทับของเราจนคุมไม่อยู่
# (U+202A-U+202E เป็น embedding/override ที่ไม่มี PDF ปิดท้ายจะรั่วไปทั้ง embed)
_BIDI_CONTROLS = re.compile(r"[‎‏؜‪-‮⁦-⁩]")

# ชื่อที่มีขึ้นบรรทัดใหม่ติดมาจะทำให้เค้าโครง 1 บรรทัด 1 ชื่อ เพี้ยนไปหมด
_WHITESPACE = re.compile(r"\s+")

# เรียงให้ภาษาที่ผู้ใช้ไทยอ่านออกขึ้นก่อน ที่เหลือไล่ตามความคุ้นตา
# ตัวที่ต้องใช้ฟอนต์สำรอง (RTL) ไปอยู่ท้ายสุด จะได้ไม่แทรกกลางรายการ
_LATIN_OR_THAI = re.compile(r"[A-Za-zÀ-ɏ฀-๿]")
_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯豈-﫿]")
_CYRILLIC_GREEK = re.compile(r"[Ͱ-ϿЀ-ӿԀ-ԯ]")

_ELLIPSIS = "…"


def clean_names(names: list[str] | None) -> list[str]:
    """ตัดค่าว่าง อักขระคุมทิศทางที่ติดมา และชื่อซ้ำออก

    ซ้ำในที่นี้ดูแค่ตัวพิมพ์เล็กใหญ่ ('Akame ga KILL!' กับ 'Akame ga Kill!'
    คือชื่อเดียวกัน) ไม่ตัดเครื่องหมายทิ้งก่อนเทียบ เพราะ '아카메가 벤다!'
    กับ '아카메가 벤다!!' เป็นคนละรายการที่ต้นทางตั้งใจแยกไว้จริง
    """
    seen: set[str] = set()
    cleaned: list[str] = []

    for name in names or []:
        if not isinstance(name, str):
            continue

        text = _WHITESPACE.sub(" ", _BIDI_CONTROLS.sub("", name)).strip()
        if not text:
            continue

        key = text.casefold()
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(text)

    return cleaned


def _script_rank(name: str) -> int:
    """จัดกลุ่มชื่อตามสคริปต์ของตัวอักษรตัวแรก

    ดูตัวอักษรตัวแรกไม่ใช่ทั้งชื่อ เพราะทิศทางของบรรทัดก็ตัดสินจากตัวนั้น
    เหมือนกัน ตัวเลขหรือเครื่องหมายนำหน้าข้ามไป ('20th Century Boys' ต้อง
    นับเป็นละติน ไม่ใช่กลุ่มไม่รู้จัก)
    """
    for ch in name:
        if not ch.isalpha():
            continue
        if _LATIN_OR_THAI.match(ch):
            return 0
        if _CJK.match(ch):
            return 1
        if _CYRILLIC_GREEK.match(ch):
            return 2
        return 3

    # ไม่มีตัวอักษรเลย เช่นชื่อที่เป็นตัวเลขล้วน - แสดงแบบ LTR ได้ปกติ
    return 0


def _isolate(name: str) -> str:
    """ห่อชื่อ 1 บรรทัดให้ทิศทางนิ่ง ไม่ว่าชื่อนั้นเป็นภาษาอะไร"""
    return f"{_LRM}{_LRI}{name}{_PDI}"


def _summary(hidden: int) -> str:
    return f"{_ELLIPSIS} และอีก {hidden} ชื่อ"


def _render(names: list[str], hidden: int) -> str:
    lines = [_isolate(name) for name in names]
    if hidden > 0:
        lines.append(_summary(hidden))
    return "\n".join(lines)


def _shorten(name: str, keep: int) -> str:
    return name[:max(keep, 1)] + _ELLIPSIS


def format_alt_names(
    names: list[str] | None,
    limit: int = FIELD_LIMIT,
    max_names: int = MAX_NAMES,
) -> str:
    """ทำ associated_names ให้พร้อมยัดใส่ค่าของ embed field

    คืนสตริงว่างเมื่อไม่เหลือชื่อให้แสดง ผู้เรียกตัดสินใจเองว่าจะซ่อนฟิลด์

    ตัดทีละบรรทัดจนพอดีลิมิต ไม่ตัดที่จำนวนตัวอักษรตรง ๆ เพราะจะตัดคาชื่อ
    และคาอักขระคุมทิศทางจนเหลือ LRI ที่ไม่มี PDI ปิด - ทิศทางจะรั่วไปทั้ง embed
    """
    cleaned = clean_names(names)
    if not cleaned:
        return ""

    # stable sort - ชื่อในกลุ่มเดียวกันยังเรียงตามลำดับที่ต้นทางให้มา
    ordered = sorted(cleaned, key=_script_rank)

    kept = ordered[:max_names]
    hidden = len(ordered) - len(kept)

    while len(kept) > 1:
        block = _render(kept, hidden)
        if len(block) <= limit:
            return block
        kept.pop()
        hidden += 1

    block = _render(kept, hidden)
    if len(block) <= limit:
        return block

    # เหลือชื่อเดียวแล้วยังยาวเกิน - ตัดที่ตัวชื่อ อักขระคุมทิศทางจึงยังครบคู่
    overflow = len(block) - limit
    return _render([_shorten(kept[0], len(kept[0]) - overflow - 1)], hidden)
