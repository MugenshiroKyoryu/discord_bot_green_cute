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
            alt_names = manga["associated_names"]

            embed = discord.Embed(
                title="Manga Titles",
                color=0x2b2d31
            )

            embed.add_field(
                name="Title",
                value=title,
                inline=False
            )

            if alt_names:

                names_text = "\n".join(alt_names)[:1000]

                embed.add_field(
                    name="Associated Names",
                    value=names_text,
                    inline=False
                )

            await interaction.response.send_message(
                embed=embed
            )

        except Exception as e:

            await interaction.response.send_message(
                f"❌ ERROR : {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Manga(bot))