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

        manga = await search_manga(name)

        if not manga:

            await interaction.response.send_message(
                "ไม่พบมังงะ"
            )
            return

        title = manga["title"]
        alt_names = manga["associated_names"]

        embed = discord.Embed(
            title=title,
            color=0x2b2d31
        )

        if alt_names:

            embed.add_field(
                name="Associated Names",
                value="\n".join(alt_names),
                inline=False
            )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):

    await bot.add_cog(
        Manga(bot)
    )