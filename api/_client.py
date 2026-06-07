import asyncio
import aiohttp

SEARCH_URL = "https://api.mangaupdates.com/v1/series/search"
SERIES_URL = "https://api.mangaupdates.com/v1/series"

_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "GreenCuteBot"
}

# กันคำสั่งแขวนถ้า API ค้าง
_TIMEOUT = aiohttp.ClientTimeout(total=15)

# จำกัดจำนวน request รายละเอียดที่ยิงพร้อมกัน เพื่อลดโอกาสโดน rate limit
_MAX_CONCURRENT = 5
_MAX_RETRIES = 3


async def _request_json(session, method, url, *, json_payload=None, error_label="API"):

    for attempt in range(_MAX_RETRIES):

        async with session.request(method, url, json=json_payload) as resp:

            if resp.status == 429 and attempt < _MAX_RETRIES - 1:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2 ** attempt
                await asyncio.sleep(min(delay, 5))
                continue

            if resp.status != 200:
                raise Exception(f"{error_label} error : {resp.status}")

            return await resp.json()

    raise Exception(f"{error_label} error : 429")


async def fetch_series_detail(
    session: aiohttp.ClientSession,
    series_id: int,
    semaphore: asyncio.Semaphore | None = None
) -> dict:

    async def _fetch():
        return await _request_json(
            session, "get", f"{SERIES_URL}/{series_id}", error_label="Series API"
        )

    if semaphore is None:
        series = await _fetch()
    else:
        async with semaphore:
            series = await _fetch()

    associated_names = [
        a["title"] for a in series.get("associated", []) if "title" in a
    ]

    anime_data = series.get("anime") or {}

    image = series.get("image") or {}
    image_url = (image.get("url") or {}).get("original")

    return {
        "title": series.get("title", "Unknown"),
        "url": series.get("url"),
        "status": series.get("status", "Unknown"),
        "type": series.get("type", "Unknown"),
        "associated_names": associated_names,
        "anime": {
            "start": anime_data.get("start", "Unknown"),
            "end": anime_data.get("end", "Unknown")
        },
        "image": image_url
    }


async def search_series(
    name: str,
    allowed_types: set[str],
    no_results_msg: str,
    no_match_msg: str
) -> list[dict]:

    async with aiohttp.ClientSession(headers=_HEADERS, timeout=_TIMEOUT) as session:

        data = await _request_json(
            session, "post", SEARCH_URL,
            json_payload={"search": name}, error_label="Search API"
        )

        results = data.get("results") or []

        if not results:
            raise Exception(no_results_msg)

        matched = [
            item["record"]["series_id"]
            for item in results
            if item.get("record", {}).get("type") in allowed_types
        ]

        if not matched:
            raise Exception(no_match_msg)

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        details = await asyncio.gather(*[
            fetch_series_detail(session, sid, semaphore) for sid in matched
        ])

        return list(details)
