import aiohttp

SEARCH_URL = "https://api.mangaupdates.com/v1/series/search"
SERIES_URL = "https://api.mangaupdates.com/v1/series"


async def search_novel(name: str):

    async with aiohttp.ClientSession() as session:

        payload = {
            "search": name
        }

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
                raise Exception("ไม่พบนิยาย")

            # ✅ filter เฉพาะ Novel
            series_id = None

            for item in data["results"]:
                record = item["record"]

                if record.get("type") and "Novel" in record.get("type"):
                    series_id = record["series_id"]
                    break

            if not series_id:
                raise Exception("ไม่พบนิยาย (เจอแต่ประเภทอื่น)")

        async with session.get(
            f"{SERIES_URL}/{series_id}"
        ) as resp:

            if resp.status != 200:
                raise Exception(f"Series API error : {resp.status}")

            series = await resp.json()

        associated_names = [
            a["title"] for a in series.get("associated", []) if "title" in a
        ]

        anime_data = series.get("anime", {})
        anime_start = anime_data.get("start", "Unknown")
        anime_end = anime_data.get("end", "Unknown")

        image_url = None
        if "image" in series and series["image"]:
            image_url = series["image"]["url"].get("original")

        return {
            "title": series.get("title", "Unknown"),
            "url": series.get("url"),
            "status": series.get("status", "Unknown"),
            "associated_names": associated_names,
            "anime": {
                "start": anime_start,
                "end": anime_end
            },
            "image": image_url
        }