from api._client import search_series


async def search_Manhwa(name: str, options: dict | None = None) -> list[dict]:
    return await search_series(
        name,
        allowed_types={"Manhwa"},
        no_results_msg="ไม่พบผลลัพธ์",
        no_match_msg="ไม่พบมังฮวา (เจอแต่ประเภทอื่น)",
        options=options
    )
