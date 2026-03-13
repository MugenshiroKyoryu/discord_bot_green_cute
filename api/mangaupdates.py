import aiohttp
from langdetect import detect

SEARCH_URL = "https://api.mangaupdates.com/v1/series/search"
SERIES_URL = "https://api.mangaupdates.com/v1/series"


def detect_language(text):

    try:
        return detect(text)
    except:
        return "unknown"


async def search_manga(name: str):

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
                raise Exception("ไม่พบมังงะ")

            series_id = data["results"][0]["record"]["series_id"]

        async with session.get(
            f"{SERIES_URL}/{series_id}"
        ) as resp:

            if resp.status != 200:
                raise Exception(f"Series API error : {resp.status}")

            series = await resp.json()

        # Associated names + language
        associated_names = []

        for a in series.get("associated", []):

            title = a["title"]

            lang = detect_language(title)

            associated_names.append({
                "title": title,
                "lang": lang
            })

        image_url = None

        if "image" in series:
            image_url = series["image"]["url"]["original"]

        result = {
            "title": series.get("title", "Unknown"),
            "url": series.get("url"),
            "status": series.get("status", "Unknown"),
            "associated_names": associated_names,
            "image": image_url
        }

        return result