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
            json=payload
        ) as resp:

            data = await resp.json()

        if not data["results"]:
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
                    "language": t["language"],
                    "title": t["title"]
                })

        return titles