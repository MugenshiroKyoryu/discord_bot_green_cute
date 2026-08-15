"""จัดตอนเริ่ม/จบของฉบับอนิเมะให้อ่านออกใน embed

MangaUpdates เก็บ anime.start กับ anime.end เป็นสตริงล้วน ไม่มีโครงสร้าง
หลายซีซั่นถูกยัดไว้ในสตริงเดียวคั่นด้วย " / " และติดป้ายซีซั่นไว้ท้ายรายการ
ในวงเล็บ ('Vol 1, Chap 0 (S1) / Vol 8, Chap 61 (S2)')

ข้อมูลจึงจัดกลุ่มคนละแกนกับที่คนอ่านต้องการ - ต้นทางแบ่งเป็น "เริ่มทั้งหมด"
กับ "จบทั้งหมด" แต่ผู้ใช้อยากรู้เป็นรายซีซั่นว่า S1 เริ่มที่ไหนจบที่ไหน
เอามาต่อกันดิบ ๆ สองบรรทัดจึงไม่มีอะไรบอกว่าบรรทัดไหนคือเริ่ม บรรทัดไหนคือจบ
และซีซั่นที่ยังไม่จบ ('Gaikotsu Kishi-sama' S2) ทำให้สองบรรทัดมีจำนวนรายการ
ไม่เท่ากันจนจับคู่ด้วยตาไม่ได้เลย

โมดูลนี้พลิกแกนกลับมาเป็นรายซีซั่น หนึ่งซีซั่นหนึ่งบรรทัด พร้อมป้ายกำกับ

แยกจาก series_view.py เพราะเป็นฟังก์ชันล้วน ไม่แตะ discord จึงเทสได้ตรง ๆ
"""

from __future__ import annotations

import re
from itertools import zip_longest

from utils._names import FIELD_LIMIT

# ตัวคั่นของต้นทางมีช่องว่างคร่อมเสมอ ตัดที่ "/" เปล่า ๆ จะไปหั่นเลขตอน
# อย่าง 'Vol 1, Chap 1/2' ขาดกลาง
_SEPARATOR = " / "

# ป้ายอยู่ท้ายรายการในวงเล็บ ส่วนใหญ่เป็น (S1) (S2) แต่มี (OVA) (Movie) ปนมาด้วย
# จึงรับอะไรก็ได้ในวงเล็บ ทิ้งไปแล้วผู้ใช้จะนึกว่า OVA เป็นซีซั่นหลัก
_LABEL = re.compile(r"\s*\(([^()]+)\)\s*$")

# ค่าที่ติด \n มาจากต้นทางทำให้เกิดบรรทัดว่างกลางฟิลด์
_WHITESPACE = re.compile(r"\s+")

# _client.py เติม "Unknown" ให้เมื่อ API ส่ง null มา ไม่ใช่ข้อมูลที่แสดงได้
_MISSING = {"", "unknown", "n/a", "none", "-"}

_ARROW = "→"
_BULLET = "·"
_NO_END = "ยังไม่จบ"
_NO_START = "ไม่ระบุ"
_ELLIPSIS = "…"


def _tokens(text: str | None) -> list[tuple[str | None, str]]:
    """แยกสตริงหนึ่งฝั่งเป็นรายการ (ป้าย, ตอน) ตามลำดับที่ต้นทางให้มา"""
    if not isinstance(text, str):
        return []

    cleaned = _WHITESPACE.sub(" ", text).strip()
    if cleaned.casefold() in _MISSING:
        return []

    tokens: list[tuple[str | None, str]] = []

    for part in cleaned.split(_SEPARATOR):
        part = part.strip()
        if not part:
            continue

        label = None
        match = _LABEL.search(part)
        if match:
            label = match.group(1).strip()
            part = part[:match.start()].strip()

        # เหลือแต่ป้ายไม่มีตอน - ไม่มีอะไรให้ผู้ใช้อ่าน
        if not part:
            continue

        tokens.append((label, part))

    return tokens


def _all_labelled(tokens: list[tuple[str | None, str]]) -> bool:
    return all(label for label, _ in tokens)


def _pair_by_label(
    starts: list[tuple[str | None, str]],
    ends: list[tuple[str | None, str]],
) -> list[tuple[str | None, str | None, str | None]]:
    """จับคู่ตามป้าย - ฝั่ง end ขาดซีซั่นที่ยังไม่จบไป ลำดับจึงเชื่อไม่ได้"""
    remaining = list(ends)
    pairs: list[tuple[str | None, str | None, str | None]] = []

    for label, body in starts:
        matched = None
        for i, (end_label, end_body) in enumerate(remaining):
            if end_label == label:
                matched = end_body
                remaining.pop(i)
                break
        pairs.append((label, body, matched))

    # ป้ายที่มีเฉพาะฝั่ง end - ผิดปกติ แต่ทิ้งข้อมูลไม่ได้
    pairs.extend((label, None, body) for label, body in remaining)

    return pairs


def _pair_by_position(
    starts: list[tuple[str | None, str]],
    ends: list[tuple[str | None, str]],
) -> list[tuple[str | None, str | None, str | None]]:
    """ไม่มีป้ายให้จับคู่ ก็เรียงตามลำดับ ดีกว่าทิ้งรายการที่เกินมา"""
    pairs: list[tuple[str | None, str | None, str | None]] = []

    for start, end in zip_longest(starts, ends):
        start_label, start_body = start or (None, None)
        end_label, end_body = end or (None, None)
        pairs.append((start_label or end_label, start_body, end_body))

    return pairs


def _line(label: str | None, start_body: str | None, end_body: str | None) -> str:
    span = f"{start_body or _NO_START} {_ARROW} {end_body or _NO_END}"
    if label:
        return f"{label} {_BULLET} {span}"
    return span


def _render(lines: list[str], hidden: int) -> str:
    shown = list(lines)
    if hidden > 0:
        shown.append(f"{_ELLIPSIS} และอีก {hidden} รายการ")
    return "\n".join(shown)


def _fit(lines: list[str], limit: int) -> str:
    """ตัดทีละบรรทัดจนพอดีลิมิต ไม่ตัดที่จำนวนตัวอักษรตรง ๆ จะได้ไม่ค้างครึ่งซีซั่น"""
    kept = list(lines)
    hidden = 0

    while len(kept) > 1:
        block = _render(kept, hidden)
        if len(block) <= limit:
            return block
        kept.pop()
        hidden += 1

    block = _render(kept, hidden)
    if len(block) <= limit:
        return block

    # เหลือบรรทัดเดียวแล้วยังยาวเกิน - ข้อมูลต้นทางเพี้ยน ตัดตรงตัวอักษรไปเลย
    return block[:max(limit - 1, 1)] + _ELLIPSIS


def format_anime_chapters(
    start: str | None,
    end: str | None,
    limit: int = FIELD_LIMIT,
) -> str:
    """ทำ anime.start/anime.end ให้พร้อมยัดใส่ค่าของ embed field

    คืนสตริงว่างเมื่อไม่มีข้อมูลอนิเมะ ผู้เรียกตัดสินใจเองว่าจะซ่อนฟิลด์
    (เรื่องส่วนใหญ่ในฐานข้อมูลไม่เคยถูกทำเป็นอนิเมะ)
    """
    starts = _tokens(start)
    ends = _tokens(end)

    if not starts and not ends:
        return ""

    if _all_labelled(starts) and _all_labelled(ends):
        pairs = _pair_by_label(starts, ends)
    else:
        pairs = _pair_by_position(starts, ends)

    return _fit([_line(*pair) for pair in pairs], limit)
