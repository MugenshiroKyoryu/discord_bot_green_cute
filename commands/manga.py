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
        description="ค้นหาชื่อมังงะ"
    )
    async def manga(self, interaction: discord.Interaction, name: str):

        try:

            manga = await search_manga(name)

            title = manga["title"]
            alt_names = manga["associated_names"]
            url = manga["url"]
            status = manga["status"]
            image = manga["image"]

            embed = discord.Embed(
                title=title,
                url=url,
                color=0x2b2d31
            )

            if image:
                embed.set_thumbnail(url=image)

            embed.add_field(
                name="สถานะ",
                value=status,
                inline=False
            )

            # แสดงชื่อ + ภาษา
            if alt_names:

                lines = []

                for item in alt_names:

                    lang_code = item["lang"]
                    lang_full = language_name(lang_code)

                    lines.append(
                        f"{item['title']} ({lang_code} {lang_full})"
                    )

                text = "\n".join(lines)

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