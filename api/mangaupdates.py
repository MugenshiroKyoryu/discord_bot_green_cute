import aiohttp

SEARCH_URL = "https://api.mangaupdates.com/v1/series/search"
SERIES_URL = "https://api.mangaupdates.com/v1/series"


async def search_manga(name: str):

    async with aiohttp.ClientSession() as session:

        payload = {
            "search": {
                "query": name
            }
        }

        async with session.post(
            SEARCH_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "GreenCuteBot"
            }
        ) as resp:

            data = await resp.json()

            print("SEARCH RESULT:", data)

            if not data.get("results"):
                return None

            series_id = data["results"][0]["record"]["series_id"]

        async with session.get(
            f"{SERIES_URL}/{series_id}"
        ) as resp:

            series = await resp.json()

        titles = []

        if "titles" in series:

            for t in series["titles"]:

                titles.append({
                    "language": t.get("language"),
                    "title": t.get("title")
                })

        return titles