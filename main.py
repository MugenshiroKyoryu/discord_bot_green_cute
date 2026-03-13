import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

from myserver import server_on

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():

    print("================================")
    print(f"Bot : {bot.user}")
    print("Bot is ready")
    print("================================")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")

    except Exception as e:
        print(e)


async def load_extensions():

    for filename in os.listdir("./commands"):

        if filename.endswith(".py"):

            await bot.load_extension(
                f"commands.{filename[:-3]}"
            )


async def main():

    server_on()

    async with bot:

        await load_extensions()
        await bot.start(TOKEN)


asyncio.run(main())