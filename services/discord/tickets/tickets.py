"""
Ticket cog for BizBot.

Provides commands for ticket functionality
"""

import discord
from discord import app_commands
from discord.ext import commands

from .ticketCategoryView import TicketCategoryView


class TicketCog(commands.Cog):
    """Ticket commands for BizBot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ticket", description="Create a help ticket")
    async def ticket(self, interaction: discord.Interaction):
        """/ticket command to create a ticket"""
        channel = interaction.channel

        category: discord.CategoryChannel | None = None
        if isinstance(channel, discord.TextChannel):
            category = channel.category
        elif isinstance(channel, discord.Thread) and isinstance(
            channel.parent, discord.TextChannel
        ):
            category = channel.parent.category

        if category is None:
            await interaction.response.send_message(
                "Please use `/ticket` inside an event category.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Select the type of help you need:",
            view=TicketCategoryView(),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    """Load the TestCog."""
    await bot.add_cog(TicketCog(bot))
