"""
Test cog for BizBot.

Provides testing commands including DynamoDB connectivity test.
"""

import discord
from discord import app_commands
from discord.ext import commands

from lib.db import db


class HealthCog(commands.Cog):
    """Testing commands for BizBot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Test bot responsiveness")
    async def ping(self, interaction: discord.Interaction):
        """Simple ping command to test if the bot is responding."""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"🏓 Pong! Latency: {latency}ms", ephemeral=True
        )

    @app_commands.command(name="db-connected", description="check db status")
    async def get_item(self, interaction: discord.Interaction):
        """
        Get a specific item from DynamoDB by ticket_id.

        Modify the key structure based on your table schema.
        """
        await interaction.response.defer(ephemeral=True)

        try:
            # Modify this key to match your table's primary key structure
            tables = []
            message = ""
            page, *_ = db.client.get_paginator("list_tables").paginate()
            if "TableNames" in page:
                tables.extend(page["TableNames"])
                message = (
                    f"✓ **[PASS] DB Status = Connected**\n"
                    f"List Tables:\n```json\n{tables}...\n```"
                )
            else:
                message = "✗ **[PASS] DB Status = Connected, unable to list tables**\n"

            await interaction.followup.send(message, ephemeral=True)

        except Exception as e:
            print(e)
            error_message = (
                "✗ **[FAIL] DB Status = Disconnected, Check AWS Credentials**\n"
            )
            await interaction.followup.send(error_message, ephemeral=True)


async def setup(bot: commands.Bot):
    """Load the TestCog."""
    await bot.add_cog(HealthCog(bot))
