# Discord Manga/Manhwa/Novel Search Bot

บอท Discord สำหรับค้นหาข้อมูล **Manga / Manhwa / Manhua / Novel** ผ่าน [MangaUpdates API](https://api.mangaupdates.com/) แสดงผลเป็น embed พร้อมปุ่มเลื่อนดูผลลัพธ์ทีละรายการ พัฒนาด้วย [discord.py](https://discordpy.readthedocs.io/) และใช้ Slash Commands ทั้งหมด

## สารบัญ

- [ฟีเจอร์](#ฟีเจอร์)
- [คำสั่ง (Slash Commands)](#คำสั่ง-slash-commands)
- [วิธีการทำงาน](#วิธีการทำงาน)
- [ข้อมูลที่แสดงใน Embed](#ข้อมูลที่แสดงใน-embed)
- [การเลื่อนดูผลลัพธ์](#การเลื่อนดูผลลัพธ์)
- [MangaUpdates API](#mangaupdates-api)
- [โครงสร้างโปรเจค](#โครงสร้างโปรเจค)
- [การติดตั้ง](#การติดตั้ง)
- [การใช้งาน](#การใช้งาน)
- [การ Deploy / Keep-Alive](#การ-deploy--keep-alive)
- [การเพิ่มคำสั่งใหม่](#การเพิ่มคำสั่งใหม่)
- [ข้อความ Error](#ข้อความ-error)
- [การแก้ปัญหา (Troubleshooting)](#การแก้ปัญหา-troubleshooting)
- [Dependencies หลัก](#dependencies-หลัก)
- [License](#license)

## ฟีเจอร์

- ค้นหาซีรีส์ด้วย Slash Commands (มี autocomplete ของ Discord ในตัว)
- กรองตามประเภท (Manga / Manhwa / Manhua / Novel) หรือค้นหารวมทุกประเภทด้วย `/series`
- แสดงผลแบบ embed: ชื่อเรื่อง (ลิงก์ไปหน้า MangaUpdates), สถานะ, ข้อมูลอนิเมะ, ชื่อที่เกี่ยวข้อง และรูปปก
- ปุ่ม **ก่อนหน้า / ถัดไป** สำหรับเลื่อนดูผลลัพธ์หลายรายการ (หมดเวลาใช้งานปุ่มใน 120 วินาที)
- ดึงรายละเอียดหลายเรื่องพร้อมกันแบบ async (`asyncio.gather`) จึงตอบเร็วแม้เจอผลลัพธ์จำนวนมาก โดยจำกัดจำนวนคำขอพร้อมกัน (สูงสุด 5) + มี timeout 15 วินาที และ retry อัตโนมัติเมื่อโดน rate limit (HTTP 429)
- เลเยอร์เรียก API ใช้โค้ดกลางร่วมกันที่ `api/_client.py` แต่ละประเภทเป็นเพียง wrapper บางๆ
- มี Flask keep-alive server ในตัว (พอร์ต 8080) สำหรับ host บนบริการที่ต้องการ HTTP endpoint

## คำสั่ง (Slash Commands)

| คำสั่ง | รายละเอียด | กรองประเภท |
|--------|------------|------------|
| `/manga <name>` | ค้นหามังงะ | `Manga` |
| `/manhwa <name>` | ค้นหามังฮวา | `Manhwa` |
| `/manhua <name>` | ค้นหามันฮัว | `Manhua` |
| `/novel <name>` | ค้นหานิยาย | `Novel` |
| `/series <name>` | ค้นหารวมทุกประเภท (แสดงฟิลด์ "ประเภท" เพิ่ม) | `Manhwa`, `Manga`, `Manhua`, `Novel` |

ทุกคำสั่งรับพารามิเตอร์ `name` (ข้อความ) เป็นคำค้นหา

## วิธีการทำงาน

ลำดับการทำงานเมื่อผู้ใช้เรียกคำสั่ง (เช่น `/manga`):

```
ผู้ใช้พิมพ์ /manga <name>
        │
        ▼
interaction.response.defer()          # ตอบ Discord ทันทีว่ากำลังประมวลผล (กันหมดเวลา 3 วิ)
        │
        ▼
search_manga(name)  ── POST /v1/series/search ──► กรอง series_id ที่ type == "Manga"
        │
        ▼
asyncio.gather(...)  ── GET /v1/series/{id} หลายตัวพร้อมกัน (จำกัด 5 พร้อมกัน) ──► รายละเอียดแต่ละเรื่อง
        │
        ▼
SeriesView(results)                   # สร้าง View + embed หน้าแรก
        │
        ▼
interaction.followup.send(embed, view)  # ส่งผลลัพธ์ให้ผู้ใช้
```

- แต่ละ command อยู่ในรูป **Cog** (`commands/*.py`) และถูกโหลดอัตโนมัติตอนบอทเริ่มทำงาน
- เลเยอร์เรียก API แยกอยู่ใน `api/*.py` โดยใช้โค้ดกลางร่วมกันที่ `api/_client.py` (จัดการ search + fetch รายละเอียด + timeout/retry/จำกัด concurrency) ส่วนการสร้าง embed/ปุ่มอยู่ใน `utils/series_view.py` — แยกหน้าที่กันชัดเจน
- หากเกิดข้อผิดพลาด cog จะส่งข้อความ error แบบ **ephemeral** (เห็นเฉพาะผู้เรียกคำสั่ง)

## ข้อมูลที่แสดงใน Embed

embed สร้างจาก `build_embed()` ใน `utils/series_view.py`:

| ฟิลด์ | ที่มาของข้อมูล | หมายเหตุ |
|-------|----------------|----------|
| ชื่อเรื่อง (title) | `title` + `url` | คลิกได้ ลิงก์ไปหน้า MangaUpdates |
| รูปปก (thumbnail) | `image` | แสดงเมื่อมีรูปเท่านั้น |
| ประเภท | `type` | แสดงเฉพาะคำสั่ง `/series` |
| เกี่ยวข้องกับผลอันดับ 1 | `relation` | แสดงเมื่อรายการนั้นมาจากสายความสัมพันธ์ เช่น `Adapted From` |
| สถานะ | `status` | เช่น Ongoing / Complete |
| อนิเมะ (ตอนที่ถูกดัดแปลง) | `anime.start`, `anime.end` | จัดรูปด้วย `format_anime_chapters()` — ซ่อนฟิลด์เมื่อไม่มีข้อมูลอนิเมะ ดูหัวข้อถัดไป |
| ชื่อที่เกี่ยวข้อง | `associated_names` | จัดรูปด้วย `format_alt_names()` — ดูหัวข้อถัดไป |
| เลขหน้า (footer) | `index / total` | บอกว่ากำลังดูผลลัพธ์ที่เท่าไรจากทั้งหมด |

## ฟิลด์ "อนิเมะ (ตอนที่ถูกดัดแปลง)"

MangaUpdates เก็บ `anime.start` กับ `anime.end` เป็น **สตริงล้วน** ไม่มีโครงสร้าง หลายซีซั่นถูกยัดไว้ในสตริงเดียว
คั่นด้วย `" / "` และติดป้ายซีซั่นไว้ท้ายรายการในวงเล็บ ข้อมูลจึงถูกจัดกลุ่มคนละแกนกับที่คนอ่านต้องการ —
ต้นทางแบ่งเป็น "เริ่มทั้งหมด" กับ "จบทั้งหมด" แต่ผู้ใช้อยากรู้เป็นรายซีซั่นว่า S1 เริ่มที่ไหนจบที่ไหน

เอามาต่อกันดิบ ๆ สองบรรทัดจะได้แบบนี้ ซึ่งไม่มีอะไรบอกว่าบรรทัดไหนคือเริ่ม บรรทัดไหนคือจบ
และซีซั่นที่ยังไม่จบ (`Gaikotsu Kishi-sama` S2) ทำให้สองบรรทัดมีรายการไม่เท่ากันจนจับคู่ด้วยตาไม่ได้:

```
Vol 1, Chap 1 (S1) / Vol 5, Chap 21 (S2)
Vol 4, Chap 20 (S1)
```

`utils/_anime.py` จึงพลิกแกนกลับมาเป็นรายซีซั่น หนึ่งซีซั่นหนึ่งบรรทัด:

```
S1 · Vol 1, Chap 1 → Vol 4, Chap 20
S2 · Vol 5, Chap 21 → ยังไม่จบ
```

| ขั้นตอน | ทำอะไร |
|---------|--------|
| ล้างข้อมูล | ยุบช่องว่าง/ขึ้นบรรทัดใหม่ที่ติดมากับค่า (ต้นเหตุของบรรทัดว่างกลางฟิลด์) และถือว่า `Unknown` / ค่าว่าง = ไม่มีข้อมูล |
| แยกรายการ | ตัดที่ `" / "` ซึ่งมีช่องว่างคร่อม ไม่ใช่ `/` เปล่า ๆ มิฉะนั้นเลขตอนอย่าง `Chap 1/2` จะขาดกลาง |
| อ่านป้าย | ดึงป้ายจากวงเล็บท้ายรายการ รับทุกค่าไม่ใช่แค่ `S1` `S2` เพราะต้นทางมี `(OVA)` `(Movie)` ปนมาด้วย |
| จับคู่ | จับตามป้ายเมื่อทุกรายการมีป้ายครบ ไม่งั้นจับตามลำดับ — ซีซั่นที่ขาดฝั่งใดฝั่งหนึ่งแสดง `ยังไม่จบ` / `ไม่ระบุ` แทนการทิ้งข้อมูล |
| จำกัดขนาด | ตัด **ทีละบรรทัด** จนพอดี `FIELD_LIMIT = 1024` แล้วต่อท้ายว่า `… และอีก N รายการ` |

ถ้าไม่เหลืออะไรให้แสดง ฟังก์ชันคืนสตริงว่างและ `build_embed()` จะ **ซ่อนฟิลด์นี้ทั้งฟิลด์** — เรื่องส่วนใหญ่
ในฐานข้อมูลไม่เคยถูกทำเป็นอนิเมะ การโชว์ `Unknown / Unknown` ทุกใบมีแต่จะรกเปล่า ๆ

เทสต์อยู่ที่ `utils/test_anime.py` (คำสั่งเดียวกับหัวข้อถัดไป)

## ฟิลด์ "ชื่อที่เกี่ยวข้อง"

`associated_names` มาคละภาษา รวมถึงภาษาที่เขียนขวาไปซ้าย (อาหรับ เปอร์เซีย ฮีบรู) ถ้าต่อด้วย `\n` ดิบ ๆ
Discord ซึ่งอยู่บน Chromium จะตัดสินทิศทางของย่อหน้า **ทีละบรรทัด** ตาม Unicode Bidirectional Algorithm
บรรทัดที่ตัวอักษรตัวแรกเป็น RTL จึงกลายเป็นย่อหน้า RTL ทั้งบรรทัด — ชิดขวา เหลือช่องว่างยาวคั่นกลางรายการ
และเครื่องหมายท้ายชื่อเด้งไปอยู่หน้าสุด (`Akame ga Kiru!` ฉบับเปอร์เซียแสดงเป็น `!آکامه گا کیل`)

`utils/_names.py` จึงจัดการให้ก่อนแสดง:

| ขั้นตอน | ทำอะไร |
|---------|--------|
| ล้างข้อมูล | ตัดค่าว่าง ยุบช่องว่าง/ขึ้นบรรทัดใหม่ในชื่อ ลบอักขระคุมทิศทางที่ติดมาจากต้นทาง |
| ตัดชื่อซ้ำ | เทียบด้วย `casefold()` — `Akame ga KILL!` กับ `Akame ga Kill!` คือชื่อเดียวกัน แต่ `아카메가 벤다!` กับ `아카메가 벤다!!` ยังแยกกัน |
| เรียงลำดับ | ละติน/ไทย → ญี่ปุ่น/เกาหลี/จีน → ซีริลลิก/กรีก → RTL และอื่น ๆ (stable — ในกลุ่มเดียวกันเรียงตามต้นทาง) |
| คุมทิศทาง | นำหน้าทุกบรรทัดด้วย `U+200E LRM` ให้ทิศย่อหน้าเป็น LTR แล้วคร่อมชื่อด้วย `U+2066 LRI` … `U+2069 PDI` |
| จำกัดขนาด | สูงสุด `MAX_NAMES = 15` ชื่อ ตัด **ทีละบรรทัด** จนพอดี `FIELD_LIMIT = 1024` แล้วต่อท้ายว่า `… และอีก N ชื่อ` |

ตัดทีละบรรทัดแทนการตัดที่จำนวนตัวอักษร เพราะการตัดกลางคันจะทิ้ง `LRI` ที่ไม่มี `PDI` ปิด แล้วทิศทางจะรั่วไปทั้ง embed

> ช่องว่าง **แนวตั้ง** รอบบรรทัดอาหรับ/ฮีบรูอาจยังเหลืออยู่บ้าง เพราะ Discord ใช้ฟอนต์สำรองที่ line-height สูงกว่า
> ส่วนนี้อยู่ฝั่ง client แก้จากบอทไม่ได้ — การเรียงลำดับกับการจำกัดจำนวนช่วยลดผลกระทบแทน

เทสต์อยู่ที่ `utils/test_names.py`:

```bash
python -m unittest discover -s utils -p "test_*.py" -v
```

## การเลื่อนดูผลลัพธ์

จัดการโดยคลาส `SeriesView` (`utils/series_view.py`):

- ปุ่ม **ก่อนหน้า** / **ถัดไป** เลื่อนดูผลลัพธ์ทีละรายการ
- ปุ่ม "ก่อนหน้า" จะถูกปิดเมื่ออยู่หน้าแรก และ "ถัดไป" ปิดเมื่ออยู่หน้าสุดท้าย
- `timeout = 120` วินาที — ครบเวลาแล้วปุ่มทั้งหมดจะถูกปิด (disable) อัตโนมัติ
- การกดปุ่มใช้ `interaction.response.edit_message` แก้ไข embed เดิมในที่เดิม ไม่ส่งข้อความใหม่

## MangaUpdates API

บอทเรียก [MangaUpdates API v1](https://api.mangaupdates.com/) (ไม่ต้องใช้ API key สำหรับการค้นหา):

| Endpoint | Method | หน้าที่ |
|----------|--------|---------|
| `/v1/series/search` | `POST` | ค้นหาด้วย `{"search": name}` คืน series_id |
| `/v1/series/{id}` | `GET` | ดึงรายละเอียดของซีรีส์รายตัว |

- ทุกคำขอส่ง header `User-Agent: GreenCuteBot`
- หลังค้นหาจะกรองผลตาม `type` ของแต่ละคำสั่ง แล้วดึงรายละเอียดที่ตรงเงื่อนไขเท่านั้น
- ผลค้นหาถูกจัดอันดับใหม่ฝั่ง client ที่ `api/_ranking.py` เพราะ API ค้นกว้างมาก (คำว่า `one piece` คืน total_hits ระดับหลักพัน) ตัวที่คะแนนชื่อต่ำกว่าเกณฑ์จะถูกตัดทิ้ง
- จากนั้นตาม `related_series` ของผลอันดับ 1 ไปดึงเรื่องเดียวกันคนละสื่อเพิ่ม (สูงสุด 3 รายการ เฉพาะความสัมพันธ์ `Adapted From` / `Alternate Version` / `Main Story`) เช่นค้นด้วยชื่อเต็มของฉบับมังงะแล้วฉบับนิยายใช้ชื่อสั้นกว่าจนคะแนนไม่ถึงเกณฑ์
- การเรียกทั้งหมดผ่าน `api/_client.py` ซึ่งมี timeout 15 วินาที, จำกัดคำขอรายละเอียดพร้อมกันสูงสุด 5 ตัว และ retry อัตโนมัติเมื่อเจอ HTTP 429 (อ่านค่า `Retry-After` ถ้ามี)

## โครงสร้างโปรเจค

```
botdiscord/
├── main.py              # จุดเริ่มต้นบอท โหลด cog และ sync slash commands
├── myserver.py          # Flask keep-alive server (พอร์ต 8080)
├── commands/            # Slash command cogs
│   ├── manga.py
│   ├── manhwa.py
│   ├── manhua.py
│   ├── novel.py
│   └── alltype.py       # คำสั่ง /series
├── api/                 # ตัวเรียก MangaUpdates API
│   ├── _client.py       # โค้ดกลาง: search + fetch รายละเอียด + timeout/retry/จำกัด concurrency
│   ├── _ranking.py      # จัดอันดับผลค้นหาใหม่ฝั่ง client (ฟังก์ชันล้วน ไม่แตะเน็ต)
│   ├── mangaupdates.py
│   ├── manhwaupdates.py
│   ├── manhuaupdates.py
│   ├── novelupdates.py
│   └── alltypeupdates.py
├── utils/
│   ├── _anime.py        # จัดตอนเริ่ม/จบของฉบับอนิเมะเป็นรายซีซั่น (ฟังก์ชันล้วน)
│   ├── _names.py        # จัดชื่อรองคละภาษา + คุมทิศทาง RTL (ฟังก์ชันล้วน)
│   └── series_view.py   # สร้าง embed และ View ปุ่มเลื่อนหน้า
├── requirements.txt
└── .env                 # เก็บ DISCORD_TOKEN (ไม่ commit)
```

## การติดตั้ง

ต้องใช้ **Python 3.10+** (โค้ดใช้ type hint แบบ `list[dict]` และ `discord.Message | None`)

1. โคลนโปรเจคและสร้าง virtual environment

   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   # source .venv/bin/activate # macOS / Linux
   ```

2. ติดตั้ง dependencies

   ```bash
   pip install -r requirements.txt
   ```

3. สร้างไฟล์ `.env` ที่ root ของโปรเจค แล้วใส่โทเคนของบอท

   ```env
   DISCORD_TOKEN=your_bot_token_here
   ```

## การใช้งาน

```bash
python main.py
```

เมื่อบอทออนไลน์จะ sync slash commands อัตโนมัติ และพิมพ์ข้อความใน console:

```
================================
Bot : YourBot#1234
Bot is ready
Synced 5 commands
================================
```

จากนั้นเรียกใช้คำสั่งเช่น `/manga` ในเซิร์ฟเวอร์ Discord ได้เลย

> **หมายเหตุ:** บอทเปิด `message_content` intent — ต้องเปิด intent นี้ใน [Discord Developer Portal](https://discord.com/developers/applications) ของบอทด้วย (Bot → Privileged Gateway Intents → Message Content Intent)

## การ Deploy / Keep-Alive

`myserver.py` รัน Flask server ที่ `0.0.0.0:8080` ใน thread แยก โดย `server_on()` ถูกเรียกใน `main()` ก่อนบอทเริ่มทำงาน:

- มี route `/` ที่ตอบ `"Server is running!"` ไว้สำหรับให้บริการ host ตรวจสอบสถานะ
- เหมาะกับการ host บนแพลตฟอร์มที่ปิด process เมื่อไม่มี HTTP traffic (เช่น Replit) โดยตั้ง uptime pinger (เช่น UptimeRobot) ยิงเข้ามาที่พอร์ตนี้เป็นระยะเพื่อให้บอทออนไลน์ตลอด
- ถ้า host บนเครื่องตัวเองหรือ VPS ไม่จำเป็นต้องใช้ keep-alive แต่ปล่อยไว้ก็ไม่กระทบการทำงาน

## การเพิ่มคำสั่งใหม่

`main.py` โหลดทุกไฟล์ `.py` ใน `./commands` อัตโนมัติ ([main.py:38-46](main.py)) ดังนั้นการเพิ่มคำสั่งใหม่ทำได้โดย:

1. สร้างตัวเรียก API ใน `api/yourtypeupdates.py` เป็น wrapper บางๆ ที่เรียก `search_series()` จาก `api/_client.py` (ลอกรูปแบบจาก `api/mangaupdates.py`):

   ```python
   from api._client import search_series


   async def search_yourtype(name: str) -> list[dict]:
       return await search_series(
           name,
           allowed_types={"YourType"},          # ค่า type ใน MangaUpdates API
           no_results_msg="ไม่พบผลลัพธ์",
           no_match_msg="ไม่พบ ... (เจอแต่ประเภทอื่น)"
       )
   ```

2. สร้าง cog ใน `commands/yourtype.py` ตามแม่แบบนี้:

   ```python
   from discord.ext import commands
   from discord import app_commands
   import discord

   from api.yourtypeupdates import search_yourtype
   from utils.series_view import SeriesView


   class YourType(commands.Cog):
       def __init__(self, bot):
           self.bot = bot

       @app_commands.command(name="yourtype", description="คำอธิบาย")
       async def yourtype(self, interaction: discord.Interaction, name: str):
           try:
               await interaction.response.defer()
               results = await search_yourtype(name)
               view = SeriesView(results)
               msg = await interaction.followup.send(embed=view.current_embed(), view=view)
               view.message = msg
           except Exception as e:
               await interaction.followup.send(f"ERROR : {str(e)}", ephemeral=True)


   async def setup(bot):
       await bot.add_cog(YourType(bot))
   ```

3. รีสตาร์ตบอท — คำสั่งจะถูกโหลดและ sync ให้อัตโนมัติ

> ถ้าต้องการให้คำสั่งแสดงฟิลด์ "ประเภท" ในผลลัพธ์ (แบบ `/series`) ให้ส่ง `SeriesView(results, show_type=True)`

## ข้อความ Error

แต่ละตัวเรียก API จะ raise ข้อความเมื่อเกิดปัญหา และ cog จะส่งให้ผู้ใช้แบบ ephemeral ในรูป `ERROR : <ข้อความ>`:

| สถานการณ์ | ข้อความ |
|-----------|---------|
| ค้นหาแล้ว API ตอบไม่สำเร็จ | `Search API error : <status>` |
| ดึงรายละเอียดไม่สำเร็จ | `Series API error : <status>` |
| โดน rate limit จน retry ครบแล้ว | `Search API error : 429` / `Series API error : 429` |
| ไม่พบผลลัพธ์เลย (`/manga`) | `ไม่พบมังงะ` |
| เจอผลแต่ไม่มีประเภทที่ต้องการ (`/manga`) | `ไม่พบมังงะ (เจอแต่ประเภทอื่น)` |
| ไม่พบผลลัพธ์ (`/manhwa`) | `ไม่พบผลลัพธ์` / `ไม่พบมังฮวา (เจอแต่ประเภทอื่น)` |
| ไม่พบผลลัพธ์ (`/manhua`) | `ไม่พบผลลัพธ์` / `ไม่พบมันฮัว (เจอแต่ประเภทอื่น)` |
| ไม่พบผลลัพธ์ (`/novel`) | `ไม่พบนิยาย` / `ไม่พบนิยาย (เจอแต่ประเภทอื่น)` |
| ไม่พบผลลัพธ์ (`/series`) | `ไม่พบ Manga / Manhwa / Manhua / Novel ที่ตรงกัน` |

## การแก้ปัญหา (Troubleshooting)

| อาการ | สาเหตุที่พบบ่อย | วิธีแก้ |
|-------|----------------|--------|
| `404 Not Found (error code: 10062): Unknown interaction` | ไม่ได้ `defer()` ภายใน 3 วินาที หรือ interaction หมดอายุ | ต้องเรียก `interaction.response.defer()` เป็นสิ่งแรกในคำสั่ง แล้วใช้ `interaction.followup.send()` ส่งผลลัพธ์ (โครงสร้างปัจจุบันทำถูกแล้ว) |
| Slash command ไม่ขึ้นใน Discord | ยังไม่ sync เสร็จ หรือเพิ่งเชิญบอทเข้าเซิร์ฟเวอร์ | รอ sync (global commands อาจใช้เวลาแพร่สักครู่) และตรวจว่า console พิมพ์ `Synced N commands` |
| บอทไม่ออนไลน์ / token error | `DISCORD_TOKEN` ใน `.env` ผิดหรือไม่มี | ตรวจไฟล์ `.env` และค่าโทเคนใน Developer Portal |
| คำสั่งใช้งานไม่ได้บางอย่าง | ไม่ได้เปิด Message Content Intent | เปิด intent ใน Developer Portal |
| คำสั่ง error เป็น `... API error : 429` บ่อย | โดน rate limit ของ MangaUpdates | บอท retry ให้อัตโนมัติแล้ว ถ้ายังเจอบ่อยให้ลดความถี่การเรียก หรือลองใหม่ภายหลัง |
| ปุ่มกดไม่ตอบสนอง | ผ่านไปเกิน 120 วินาที (timeout) | เรียกคำสั่งใหม่อีกครั้ง |

## Dependencies หลัก

- [discord.py](https://discordpy.readthedocs.io/) `2.7.1` — ไลบรารีหลักของบอท
- [aiohttp](https://docs.aiohttp.org/) — เรียก MangaUpdates API แบบ async
- [Flask](https://flask.palletsprojects.com/) — keep-alive server
- [python-dotenv](https://pypi.org/project/python-dotenv/) — โหลดค่าจากไฟล์ `.env`

รายการเต็มดูได้ที่ [requirements.txt](requirements.txt)

## License

ดูรายละเอียดในไฟล์ [LICENSE](LICENSE)
