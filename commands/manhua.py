from discord.ext import commands
from discord import app_commands
import discord

from api.manhuaupdates import search_Manhua
from utils.series_view import SeriesView


class Manhua(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="manhua",
        description="ค้นหามันฮัว"
    )
    async def manhua(self, interaction: discord.Interaction, name: str):

        try:

            await interaction.response.defer()

            results = await search_Manhua(name)
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
    await bot.add_cog(Manhua(bot))
