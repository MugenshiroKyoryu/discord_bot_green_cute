from api._client import search_series


async def search_Manhua(name: str, options: dict | None = None) -> list[dict]:
    return await search_series(
        name,
        allowed_types={"Manhua"},
        no_results_msg="ไม่พบผลลัพธ์",
        no_match_msg="ไม่พบมันฮัว (เจอแต่ประเภทอื่น)",
        options=options
    )
