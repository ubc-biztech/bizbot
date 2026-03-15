"""
Discord bot client for BizBot.

Initializes the discord.py bot with necessary intents and loads cogs.
"""

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from db import db_client


# Load environment variables
# Bot setup with intents
# If you get PrivilegedIntentsRequired errors, enable these in Discord Developer Portal:
# https://discord.com/developers/applications/ → Your App → Bot → Privileged Gateway Intents
intents = discord.Intents.default()
intents.guilds = True  # Required for basic bot functionality
intents.message_content = True  # Uncomment if you need to read message content
intents.members = True  # Uncomment if you need member verification/join events

bot = commands.Bot(
    command_prefix="!",  # Fallback prefix (mainly using slash commands)
    intents=intents,
    description="BizBot - Internal Discord bot for BizTech event support",
)


@bot.event
async def on_ready():
    """Called when the bot successfully connects to Discord."""
    if bot.user:
        print(f"✓ Bot logged in as {bot.user} (ID: {bot.user.id})")
    print(f"✓ Connected to {len(bot.guilds)} guild(s)")

    # Sync slash commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f"✓ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"✗ Failed to sync commands: {e}")


@bot.event
async def on_guild_join(guild):
    """Called when the bot joins a new guild."""
    print(f"✓ Joined guild: {guild.name} (ID: {guild.id})")


@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands."""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        print(f"Command error: {error}")
        await ctx.send("An error occurred while processing your command.")


async def load_cogs():
    """Load all cogs from the cogs directory."""
    cogs_to_load = [
        "bots.cogs.test",
        # Add more cogs here as you create them:
        # "bots.cogs.verify",
        # "bots.cogs.tickets",
    ]

    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f"✓ Loaded cog: {cog}")
        except Exception as e:
            print(f"✗ Failed to load cog {cog}: {e}")


async def start_bot():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN not found in environment variables")

    await load_cogs()

    try:
        await bot.start(token)
    except discord.errors.PrivilegedIntentsRequired as e:
        print(e)
        raise


async def stop_bot():
    """Gracefully stop the bot."""
    await bot.close()
