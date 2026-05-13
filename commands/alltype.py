from discord.ext import commands
from discord import app_commands
import discord

from api.alltypeupdates import search_Series


class Series(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="series",
        description="ค้นหา Manga / Manhwa / Manhua / Novel"
    )
    async def series(self, interaction: discord.Interaction, name: str):

        try:

            series = await search_Series(name)

            title = series["title"]
            alt_names = series["associated_names"]
            url = series["url"]
            status = series["status"]
            image = series["image"]
            series_type = series.get("type", "Unknown")
            anime = series.get("anime", {})

            anime_start = anime.get("start", "Unknown")
            anime_end = anime.get("end", "Unknown")

            embed = discord.Embed(
                title=title,
                url=url,
                color=0x2b2d31
            )

            if image:
                embed.set_thumbnail(url=image)

            embed.add_field(
                name="ประเภท",
                value=series_type,
                inline=True
            )

            embed.add_field(
                name="สถานะ",
                value=status,
                inline=True
            )

            embed.add_field(
                name="อนิเมะ Start/End Chapter",
                value=f"{anime_start}\n{anime_end}",
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
    await bot.add_cog(Series(bot))
