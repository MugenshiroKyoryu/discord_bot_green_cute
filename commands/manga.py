from discord.ext import commands
from discord import app_commands
import discord

from api.mangaupdates import search_manga
from utils.series_view import SeriesView


class Manga(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="manga",
        description="ค้นหาชื่อมังงะ"
    )
    async def manga(self, interaction: discord.Interaction, name: str):

        try:

            await interaction.response.defer()

            results = await search_manga(name)
            view = SeriesView(results)

            await interaction.followup.send(
                embed=view.current_embed(),
                view=view
            )

        except Exception as e:

            await interaction.followup.send(
                f"ERROR : {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Manga(bot))