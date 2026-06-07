from api._client import search_series

ALLOWED_TYPES = {"Manhwa", "Manga", "Manhua", "Novel"}


async def search_Series(name: str) -> list[dict]:
    return await search_series(
        name,
        allowed_types=ALLOWED_TYPES,
        no_results_msg="ไม่พบผลลัพธ์",
        no_match_msg="ไม่พบ Manga / Manhwa / Manhua / Novel ที่ตรงกัน"
    )
