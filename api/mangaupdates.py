import aiohttp

SEARCH_URL = "https://api.mangaupdates.com/v1/series/search"
SERIES_URL = "https://api.mangaupdates.com/v1/series"


async def search_manga(name: str):

    async with aiohttp.ClientSession() as session:

        # -------------------------
        # STEP 1 : Search manga
        # -------------------------
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

            if "results" not in data:
                raise Exception("API response ไม่มี field results")

            if not data["results"]:
                raise Exception("ไม่พบมังงะ")

            series_id = data["results"][0]["record"]["series_id"]

        # -------------------------
        # STEP 2 : Get series detail
        # -------------------------
        async with session.get(
            f"{SERIES_URL}/{series_id}"
        ) as resp:

            if resp.status != 200:
                raise Exception(f"Series API error : {resp.status}")

            series = await resp.json()

        # -------------------------
        # Associated names
        # -------------------------
        associated_names = [
            a["title"] for a in series.get("associated", [])
        ]

        # -------------------------
        # Image
        # -------------------------
        image_url = None

        if "image" in series:
            image_url = series["image"]["url"]["original"]

        # -------------------------
        # Result
        # -------------------------
        result = {
            "title": series.get("title", "Unknown"),
            "url": series.get("url"),
            "status": series.get("status", "Unknown"),
            "associated_names": associated_names,
            "image": image_url
        }

        return result