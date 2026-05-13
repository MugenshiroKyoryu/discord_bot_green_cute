import aiohttp

SEARCH_URL = "https://api.mangaupdates.com/v1/series/search"
SERIES_URL = "https://api.mangaupdates.com/v1/series"


async def fetch_series_detail(session: aiohttp.ClientSession, series_id: int) -> dict:

    async with session.get(f"{SERIES_URL}/{series_id}") as resp:

        if resp.status != 200:
            raise Exception(f"Series API error : {resp.status}")

        series = await resp.json()

    associated_names = [
        a["title"] for a in series.get("associated", []) if "title" in a
    ]

    anime_data = series.get("anime", {})

    image_url = None
    if "image" in series and series["image"]:
        image_url = series["image"]["url"].get("original")

    return {
        "title": series.get("title", "Unknown"),
        "url": series.get("url"),
        "status": series.get("status", "Unknown"),
        "associated_names": associated_names,
        "anime": {
            "start": anime_data.get("start", "Unknown"),
            "end": anime_data.get("end", "Unknown")
        },
        "image": image_url
    }


async def search_Manhwa(name: str) -> list[dict]:

    async with aiohttp.ClientSession() as session:

        payload = {"search": name}

        async with session.post(
            SEARCH_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "GreenCuteBot"
            }
        ) as resp:

            if resp.status != 200:
                raise Exception(f"Search API error : {resp.status}")

            data = await resp.json()

            if not data["results"]:
                raise Exception("ไม่พบผลลัพธ์")

            matched = [
                item["record"]["series_id"]
                for item in data["results"]
                if item["record"].get("type") == "Manhwa"
            ]

            if not matched:
                raise Exception("ไม่พบมังฮวา (เจอแต่ประเภทอื่น)")

        results = []
        for series_id in matched:
            detail = await fetch_series_detail(session, series_id)
            results.append(detail)

        return results