import discord


def build_embed(data: dict, index: int, total: int, show_type: bool = False) -> discord.Embed:

    title = data["title"]
    url = data["url"]
    status = data["status"]
    image = data["image"]
    alt_names = data["associated_names"]
    anime = data.get("anime", {})
    anime_start = anime.get("start", "Unknown")
    anime_end = anime.get("end", "Unknown")

    embed = discord.Embed(
        title=title,
        url=url,
        color=0x2b2d31
    )

    embed.set_footer(text=f"{index + 1} / {total}")

    if image:
        embed.set_thumbnail(url=image)

    if show_type:
        embed.add_field(
            name="ประเภท",
            value=data.get("type", "Unknown"),
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

    return embed


class SeriesView(discord.ui.View):

    def __init__(self, results: list[dict], show_type: bool = False):
        super().__init__(timeout=120)
        self.results = results
        self.index = 0
        self.show_type = show_type
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.index == 0
        self.next_button.disabled = self.index == len(self.results) - 1

    def current_embed(self) -> discord.Embed:
        return build_embed(self.results[self.index], self.index, len(self.results), self.show_type)

    @discord.ui.button(label="ก่อนหน้า", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="ถัดไป", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)