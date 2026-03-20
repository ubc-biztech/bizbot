"""
Test cog for BizBot.

Provides testing commands including DynamoDB connectivity test.
"""

import discord
from discord import app_commands
from discord.ext import commands


from lib.db import db


class AdminCog(commands.Cog):
    """Testing commands for BizBot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="admin", description="Test bot responsiveness")
    async def overview(self, interaction: discord.Interaction):
        """Simple ping command to test if the bot is responding."""
        await interaction.response.send_modal(ConfigCreateModal(None))

    @app_commands.command(name="admin-event-new", description="Create new event")
    async def newEvent(
            self,
            interaction: discord.Interaction,
            event_name: str, 
            year: int,
            role: discord.Role,
            mentor_role: discord.Role
            
    ):
        await interaction.response.send_message(
                f"selected: {event_name}, role{role}, mentor{mentor_role}")

    @app_commands.command(name="admin-event-archive", description="Archive event")
    async def newEvent(
            self,
            interaction: discord.Interaction,
            event_name: str, 
            year: int,
            
    ):
        await interaction.response.send_message(
                f"archived: {event_name}{year}")


        


async def setup(bot: commands.Bot):
    """Load the TestCog."""
    await bot.add_cog(AdminCog(bot))
