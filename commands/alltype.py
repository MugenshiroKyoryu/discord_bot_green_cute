from discord.ext import commands
from discord import app_commands
import discord

from api.alltypeupdates import search_Series
from utils.search_options import FILTER_CHOICES, build_options
from utils.series_view import SeriesView


class Series(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="series",
        description="ค้นหา Manga / Manhwa / Manhua / Novel"
    )
    @app_commands.describe(
        name="ชื่อเรื่องที่ต้องการค้นหา",
        year="ปีที่ออก เช่น 2015",
        genre="แนวที่ต้องการ คั่นด้วย , เช่น Action, Fantasy",
        exclude_genre="แนวที่ไม่ต้องการ คั่นด้วย ,",
        filter="ตัวกรองเพิ่มเติม"
    )
    @app_commands.choices(filter=FILTER_CHOICES)
    async def series(
        self,
        interaction: discord.Interaction,
        name: str,
        year: str | None = None,
        genre: str | None = None,
        exclude_genre: str | None = None,
        filter: app_commands.Choice[str] | None = None
    ):

        try:

            await interaction.response.defer()

            options = build_options(
                year=year,
                genre=genre,
                exclude_genre=exclude_genre,
                filters=filter.value if filter else None
            )

            results = await search_Series(name, options)
            view = SeriesView(results, show_type=True)

            msg = await interaction.followup.send(
                embed=view.current_embed(),
                view=view
            )
            view.message = msg

        except Exception as e:

            await interaction.followup.send(
                f"ERROR : {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Series(bot))