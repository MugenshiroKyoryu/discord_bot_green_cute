from api._client import search_series


async def search_manga(name: str) -> list[dict]:
    return await search_series(
        name,
        allowed_types={"Manga"},
        no_results_msg="ไม่พบมังงะ",
        no_match_msg="ไม่พบมังงะ (เจอแต่ประเภทอื่น)"
    )
