"""
Test cog for BizBot.

Provides testing commands including DynamoDB connectivity test.
"""

import discord
from discord import app_commands
from discord.ext import commands
from bots.constants import TICKETS_TABLE
from bots.db import db


class TestCog(commands.Cog):
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

    @app_commands.command(
        name="get-item", description="Get a specific item from DynamoDB"
    )
    @app_commands.describe(ticket_id="The ticket ID to retrieve")
    async def get_item(self, interaction: discord.Interaction, ticket_id: str):
        """
        Get a specific item from DynamoDB by ticket_id.

        Modify the key structure based on your table schema.
        """
        await interaction.response.defer(ephemeral=True)

        try:
            # Modify this key to match your table's primary key structure
            item = await db.get_one_custom(
                {
                    "TableName": TICKETS_TABLE,
                    "Key": {
                        "ticketID": {"S": ticket_id},
                        "eventID;year": {"S": "produhacks;2026"},
                    },
                }
            )

            if item:
                message = f"✓ **Item Found**\n```json\n{item}\n```"
            else:
                message = f"✗ **Item Not Found**\nNo item with ticket_id `{ticket_id}` exists."

            await interaction.followup.send(message, ephemeral=True)

        except Exception as e:
            error_message = f"✗ **Query Failed**\nError: ```{str(e)}```"
            await interaction.followup.send(error_message, ephemeral=True)


async def setup(bot: commands.Bot):
    """Load the TestCog."""
    await bot.add_cog(TestCog(bot))
