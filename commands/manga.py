from discord.ext import commands
from discord import app_commands
import discord

from api.mangaupdates import search_manga
from utils.language import language_name


class Manga(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(
        name="manga",
        description="ค้นหาชื่อมังงะในหลายภาษา"
    )
    async def manga(
        self,
        interaction: discord.Interaction,
        name: str
    ):

        titles = await search_manga(name)

        if not titles:

            await interaction.response.send_message(
                "ไม่พบมังงะ"
            )
            return

        embed = discord.Embed(
            title="ชื่อมังงะในแต่ละภาษา"
        )

        for t in titles:

            lang_code = t["language"]
            title = t["title"]

            lang = language_name(lang_code)

            embed.add_field(
                name=lang,
                value=title,
                inline=False
            )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):

    await bot.add_cog(
        Manga(bot)
    )