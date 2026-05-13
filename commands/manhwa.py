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

            results = await search_Manhwa(name)
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
    await bot.add_cog(Manhwa(bot))