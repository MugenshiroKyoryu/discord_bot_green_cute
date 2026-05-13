from discord.ext import commands
from discord import app_commands
import discord

from api.alltypeupdates import search_Series
from utils.series_view import SeriesView


class Series(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="series",
        description="ค้นหา Manga / Manhwa / Manhua / Novel"
    )
    async def series(self, interaction: discord.Interaction, name: str):

        try:

            results = await search_Series(name)
            view = SeriesView(results, show_type=True)

            await interaction.response.send_message(
                embed=view.current_embed(),
                view=view
            )

        except Exception as e:

            await interaction.response.send_message(
                f"ERROR : {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Series(bot))