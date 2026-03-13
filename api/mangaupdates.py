import aiohttp

SEARCH_URL = "https://api.mangaupdates.com/v1/series/search"
SERIES_URL = "https://api.mangaupdates.com/v1/series"


async def search_manga(name: str):

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

            if not data.get("results"):
                raise Exception("ไม่พบมังงะ")

            record = data["results"][0]["record"]

            series_id = record["series_id"]

            # associated names จาก search
            associated = record.get("associated_names", [])

        async with session.get(
            f"{SERIES_URL}/{series_id}"
        ) as resp:

            if resp.status != 200:
                raise Exception(f"Series API error : {resp.status}")

            series = await resp.json()

        title = series.get("title", "Unknown")

        # รวมชื่อทั้งหมด (แต่ไม่ซ้ำ)
        names = list(dict.fromkeys(associated))

        return {
            "title": title,
            "associated_names": names
        }