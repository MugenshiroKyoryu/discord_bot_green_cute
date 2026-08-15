import discord

from utils._names import format_alt_names


def build_embed(data: dict, index: int, total: int, show_type: bool = False) -> discord.Embed:

    title = data["title"]
    url = data["url"]
    status = data["status"]
    image = data["image"]
    alt_names = data["associated_names"]
    anime = data.get("anime", {})
    anime_start = anime.get("start", "Unknown")
    anime_end = anime.get("end", "Unknown")
    total_hits = data.get("total_hits")
    relation = data.get("relation")

    embed = discord.Embed(
        title=title,
        url=url,
        color=0x2b2d31
    )

    # บอกด้วยว่าค้นเจอทั้งหมดกี่เรื่อง เพราะเราตัดมาแสดงแค่ส่วนบนของอันดับ
    footer = f"{index + 1} / {total}"
    if total_hits and total_hits > total:
        footer += f" · พบทั้งหมด {total_hits} เรื่อง"

    embed.set_footer(text=footer)

    if image:
        embed.set_thumbnail(url=image)

    if show_type:
        embed.add_field(
            name="ประเภท",
            value=data.get("type", "Unknown"),
            inline=True
        )

    # เรื่องนี้ไม่ได้ติดมาจากชื่อ แต่มาจากสายความสัมพันธ์ของผลอันดับ 1
    # ต้องบอก ไม่งั้นผู้ใช้จะงงว่าทำไมชื่อไม่ตรงกับที่พิมพ์
    if relation:
        embed.add_field(
            name="เกี่ยวข้องกับผลอันดับ 1",
            value=relation,
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

    # ต้องผ่าน format_alt_names ก่อนเสมอ ต่อเองด้วย "\n" แล้วชื่อภาษาที่เขียน
    # ขวาไปซ้ายจะดึงทั้งบรรทัดไปชิดขวา เหลือช่องว่างยาวคั่นกลางรายการ
    text = format_alt_names(alt_names)
    if text:
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
        self.message: discord.Message | None = None
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.index == 0
        self.next_button.disabled = self.index == len(self.results) - 1

    def current_embed(self) -> discord.Embed:
        return build_embed(self.results[self.index], self.index, len(self.results), self.show_type)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

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