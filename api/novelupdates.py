from api._client import search_series


async def search_novel(name: str, options: dict | None = None) -> list[dict]:
    return await search_series(
        name,
        allowed_types={"Novel"},
        no_results_msg="ไม่พบนิยาย",
        no_match_msg="ไม่พบนิยาย (เจอแต่ประเภทอื่น)",
        options=options
    )
