from discord.ext import commands
from discord import app_commands
import discord

from api.manhwaupdates import search_Manhwa
from utils.series_view import SeriesView


class Manhwa(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="manhwa",
        description="ค้นหามังฮวา"
    )
    async def manhwa(self, interaction: discord.Interaction, name: str):

        try:

            await interaction.response.defer()

            results = await search_Manhwa(name)
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
    await bot.add_cog(Manhwa(bot))