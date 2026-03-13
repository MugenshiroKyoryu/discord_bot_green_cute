from discord.ext import commands
from discord import app_commands
import discord

from api.mangaupdates import search_manga


class Manga(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(
        name="manga",
        description="ค้นหาชื่อมังงะ"
    )
    async def manga(
        self,
        interaction: discord.Interaction,
        name: str
    ):

        try:

            manga = await search_manga(name)

            title = manga["title"]
            names = manga["all_names"]

            # ป้องกัน embed limit
            names_text = "\n".join(names)[:1000]

            embed = discord.Embed(
                title=title,
                color=0x2b2d31
            )

            embed.add_field(
                name="All Titles",
                value=names_text,
                inline=False
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:

            await interaction.response.send_message(
                f"❌ ERROR : {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Manga(bot))