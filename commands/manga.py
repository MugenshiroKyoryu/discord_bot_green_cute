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
    async def manga(self, interaction: discord.Interaction, name: str):

        try:

            manga = await search_manga(name)

            title = manga["title"]
            alt_names = manga["associated_names"]
            url = manga["url"]
            status = manga["status"]

            embed = discord.Embed(
                title=title,
                url=url,
                color=0x2b2d31
            )

            embed.add_field(
                name="สถานะ",
                value=status,
                inline=False
            )

            if alt_names:

                text = "\n".join(alt_names)

                if len(text) > 1024:
                    text = text[:1020] + "..."

                embed.add_field(
                    name="ชื่อที่เกี่ยวข้อง",
                    value=text,
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