from discord.ext import commands
from discord import app_commands
import discord

from api.novelupdates import search_novel
from utils.series_view import SeriesView


class Novel(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="novel",
        description="ค้นหานิยาย"
    )
    async def novel(self, interaction: discord.Interaction, name: str):

        try:

            results = await search_novel(name)
            view = SeriesView(results)

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
    await bot.add_cog(Novel(bot))