from discord.ext import commands
from discord import app_commands
import discord

from api.novelupdates import search_novel  # ✅ เปลี่ยน


class Novel(commands.Cog):  # ✅ เปลี่ยนชื่อ class

    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(
        name="novel",  # ✅ เปลี่ยน command
        description="ค้นหานิยาย"
    )
    async def novel(self, interaction: discord.Interaction, name: str):

        try:

            novel = await search_novel(name)  # ✅ เปลี่ยน function

            title = novel["title"]
            alt_names = novel["associated_names"]
            url = novel["url"]
            status = novel["status"]
            image = novel["image"]
            anime = novel.get("anime", {})

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
    await bot.add_cog(Novel(bot))  # ✅ เปลี่ยน class