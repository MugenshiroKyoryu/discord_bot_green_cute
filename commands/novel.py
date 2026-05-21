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

            await interaction.response.defer()

            results = await search_novel(name)
            view = SeriesView(results)

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
    await bot.add_cog(Novel(bot))