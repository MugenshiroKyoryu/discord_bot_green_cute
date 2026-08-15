"""จัดอันดับผลค้นหาใหม่ฝั่ง client

MangaUpdates ค้นกว้างมาก คำว่า "one piece" คืน total_hits ระดับ 8,900 เรื่อง
และบางรายการติดมาเพราะชื่อรองบังเอิญมีคำซ้ำ เช่น 'Fuufu no Uragao'
ที่ติดมาจาก hit_title 'One & One' โมดูลนี้ให้คะแนนความใกล้เคียงของชื่อ
เพื่อดันตัวที่ตรงจริงขึ้นก่อน แล้วตัดตัวที่อ่อนกว่าเกณฑ์ทิ้ง

แยกจาก _client.py เพราะเป็นฟังก์ชันล้วน ไม่แตะเน็ต จึงเทสได้ตรง ๆ
"""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher

# คะแนนชื่อต่ำกว่านี้ถือว่าไม่ใช่สิ่งที่ผู้ใช้หา
MATCH_FLOOR = 0.6

# token ที่ใกล้กันไม่ถึงเกณฑ์นี้ไม่นับว่าตรง กัน 'piece' ไปแมตช์ 'one'
# แต่ยังหลวมพอให้ 'pece' ที่พิมพ์ผิดแมตช์ 'piece' ได้
_TOKEN_FLOOR = 0.7

# ความนิยมใช้ตัดสินเฉพาะตอนคะแนนชื่อเท่ากัน จึงถ่วงน้ำหนักไว้ต่ำมาก
_POPULARITY_WEIGHT = 0.05

# ตัดทุกอย่างที่ไม่ใช่ตัวอักษร/ตัวเลข เพราะ '&' ':' '-' ในชื่อเรื่องไม่มีผลกับความหมาย
_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)


def normalize(text: str | None) -> str:
    """ทำชื่อให้เทียบกันได้ - ตัวพิมพ์เล็ก ไม่มีเครื่องหมาย ช่องว่างเดียว"""
    if not text:
        return ""
    return _NON_WORD.sub(" ", text.casefold()).strip()


def _token_score(query_token: str, candidate_tokens: list[str]) -> float:
    """คะแนนของคำค้น 1 คำ เทียบกับคำที่ใกล้ที่สุดในชื่อเรื่อง"""
    best = 0.0
    for token in candidate_tokens:
        if token == query_token:
            return 1.0
        ratio = SequenceMatcher(None, query_token, token).ratio()
        if ratio > best:
            best = ratio
    return best if best >= _TOKEN_FLOOR else 0.0


def text_score(query_norm: str, query_tokens: list[str], candidate: str | None) -> float:
    """0.0-1.0 บอกว่าชื่อ candidate ตรงกับคำค้นแค่ไหน"""
    cand = normalize(candidate)
    if not cand or not query_tokens:
        return 0.0

    cand_tokens = cand.split()
    coverage = sum(_token_score(t, cand_tokens) for t in query_tokens) / len(query_tokens)

    # ไม่มีคำไหนตรงเลย ไม่ต้องไปดูต่อ
    if coverage <= 0.0:
        return 0.0

    if cand == query_norm:
        return 1.0

    score = coverage * 0.8

    # ชื่อที่ขึ้นต้นด้วยคำค้นเต็ม ๆ มักใช่กว่าชื่อที่มีคำค้นแทรกอยู่กลาง
    if cand.startswith(query_norm + " "):
        score = max(score, 0.9)
    elif query_norm in cand:
        score = max(score, 0.85)

    return score


def _popularity(record: dict) -> float:
    """0.0-1.0 จากจำนวนโหวตและคะแนน ใช้เป็นตัวตัดสินตอนคะแนนชื่อเท่ากัน"""
    votes = record.get("rating_votes") or 0
    rating = record.get("bayesian_rating") or 0.0
    if votes <= 0:
        return 0.0

    # log กันเรื่องดังมาก ๆ ถ่างคะแนนจนตัวอื่นไม่มีความหมาย
    weight = min(math.log10(votes + 1) / 4.0, 1.0)
    return weight * (rating / 10.0 if rating else 0.5)


def _match(query_norm: str, query_tokens: list[str], item: dict) -> float:
    """เอาคะแนนที่ดีที่สุดระหว่างชื่อหลักกับชื่อที่ API บอกว่าตรง (hit_title)"""
    record = item.get("record") or {}
    return max(
        text_score(query_norm, query_tokens, record.get("title")),
        text_score(query_norm, query_tokens, item.get("hit_title")),
    )


def score_item(query: str, item: dict) -> float:
    """คะแนนของผลลัพธ์ 1 รายการ - แยกออกมาให้เรียกตรวจทีละตัวได้"""
    query_norm = normalize(query)
    return _match(query_norm, query_norm.split(), item)


def rank(
    query: str,
    items: list[dict],
    *,
    limit: int,
    floor: float = MATCH_FLOOR
) -> list[dict]:
    """เรียงผลใหม่ตามความตรงกับคำค้น ตัดตัวที่อ่อนเกินเกณฑ์ แล้วคืนไม่เกิน limit"""
    query_norm = normalize(query)
    query_tokens = query_norm.split()

    scored = []
    for item in items:
        match = _match(query_norm, query_tokens, item)
        popularity = _popularity(item.get("record") or {})
        scored.append((match, match + popularity * _POPULARITY_WEIGHT, item))

    kept = [row for row in scored if row[0] >= floor]

    if not kept:
        # ไม่มีใครผ่านเกณฑ์ - คืนลำดับเดิมของ API ดีกว่าคืนค่าว่าง
        # เพราะ API เรียงตาม relevance อยู่แล้ว และคำค้นที่พิมพ์ผิดหนัก ๆ
        # ก็ยังมีโอกาสได้ของที่ถูกจากอันดับต้น ๆ
        return [item for _, _, item in scored[:limit]]

    # sort เสถียร ตัวที่คะแนนเท่ากันจึงคงลำดับ relevance เดิมของ API ไว้
    kept.sort(key=lambda row: row[1], reverse=True)
    return [item for _, _, item in kept[:limit]]
