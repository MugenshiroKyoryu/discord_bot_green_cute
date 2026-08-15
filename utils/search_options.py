"""แปลงตัวเลือกจาก slash command เป็น payload ของ POST /series/search

ชื่อฟิลด์และค่าที่รับได้อ้างอิง SeriesSearchRequestV1 ในสเปก ถ้าใส่ค่านอกนี้
API จะตอบ 400 พร้อมบอกฟิลด์ที่ผิดมา และ _client จะแปลข้อความนั้นให้ผู้ใช้อ่านต่อ
"""

from discord import app_commands

# ตาม enum ของ SeriesSearchRequestV1.filters
FILTER_CHOICES = [
    app_commands.Choice(name="มีสแกนแปลแล้ว", value="scanlated"),
    app_commands.Choice(name="จบแล้ว", value="completed"),
    app_commands.Choice(name="เฉพาะ oneshot", value="oneshots"),
    app_commands.Choice(name="ไม่เอา oneshot", value="no_oneshots"),
    app_commands.Choice(name="มีตอนออกแล้ว", value="some_releases"),
    app_commands.Choice(name="ยังไม่มีตอนออก", value="no_releases"),
]


def _split(text: str | None) -> list[str]:
    """รับแนวคั่นด้วยจุลภาคจากผู้ใช้ เช่น 'Action, Fantasy' -> ['Action', 'Fantasy']"""
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def build_options(
    year: str | None = None,
    genre: str | None = None,
    exclude_genre: str | None = None,
    filters: str | None = None
) -> dict:
    """คืนเฉพาะฟิลด์ที่ผู้ใช้กรอกจริง ฟิลด์ว่างไม่ส่งไปกวน API"""
    options: dict = {}

    year = (year or "").strip()
    if year:
        options["year"] = year

    genres = _split(genre)
    if genres:
        options["genre"] = genres

    excluded = _split(exclude_genre)
    if excluded:
        options["exclude_genre"] = excluded

    if filters:
        # สเปกรับเป็น array แม้ Discord จะให้เลือกได้ทีละอัน
        options["filters"] = [filters]

    return options
