import aiohttp

SEARCH_URL = "https://api.mangaupdates.com/v1/series/search"
SERIES_URL = "https://api.mangaupdates.com/v1/series"


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

            print("SEARCH RESULT:", data)

            if "results" not in data:
                raise Exception("API response ไม่มี field results")

            if not data["results"]:
                raise Exception("ไม่พบมังงะ")

            series_id = data["results"][0]["record"]["series_id"]

        async with session.get(
            f"{SERIES_URL}/{series_id}"
        ) as resp:

            if resp.status != 200:
                raise Exception(f"Series API error : {resp.status}")

            series = await resp.json()

        title = series.get("title", "Unknown")
        alt_names = series.get("associated_names", [])

        # รวมชื่อทั้งหมด
        all_names = [title] + alt_names

        return {
            "title": title,
            "all_names": all_names
        }