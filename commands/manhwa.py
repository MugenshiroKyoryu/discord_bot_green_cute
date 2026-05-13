from discord.ext import commands
from discord import app_commands
import discord

from api.manhwaupdates import search_Manhwa


class Manhwa(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="manhwa",
        description="ค้นหามังฮวา"
    )
    async def manhwa(self, interaction: discord.Interaction, name: str):

        try:

            manhwa = await search_Manhwa(name)

            title = manhwa["title"]
            alt_names = manhwa["associated_names"]
            url = manhwa["url"]
            status = manhwa["status"]
            image = manhwa["image"]
            anime = manhwa.get("anime", {})

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
                name="สถานะ",
                value=status,
                inline=False
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
    await bot.add_cog(Manhwa(bot))
