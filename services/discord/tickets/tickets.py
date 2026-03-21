"""
Ticket cog for BizBot.

Provides commands for ticket functionality
"""

import re

import discord
from boto3.dynamodb.conditions import Key
from discord import app_commands
from discord.ext import commands

from lib.constants import TICKETS_TABLE
from lib.db import db

from .ticketCategoryView import TicketCategoryView
from .ticketCloseConfirmView import TicketCloseConfirmView


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
                "Please use `/ticket` inside an event category.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Select the type of help you need:",
            view=TicketCategoryView(),
            ephemeral=True,
        )

    @app_commands.command(name="close", description="Close the current ticket channel")
    async def close(self, interaction: discord.Interaction):
        """/close command to start ticket close flow."""
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "You can't use `/close` in this channel.", ephemeral=True
            )
            return

        category = channel.category
        if category is None:
            await interaction.response.send_message(
                "You can't use `/close` in this channel.", ephemeral=True
            )
            return

        channel_match = re.fullmatch(r"ticket-(\d+)", channel.name)
        if channel_match is None:
            await interaction.response.send_message(
                "You can't use `/close` in this channel.", ephemeral=True
            )
            return

        ticket_id = channel_match.group(1)
        category_name = category.name

        # validate ticket_id and eventID;year against db
        try:
            table = db._get_table(TICKETS_TABLE)
            query_response = table.query(
                KeyConditionExpression=Key("ticketID").eq(ticket_id)
                & Key("eventID;year").begins_with(f"{category_name};"),
                Limit=1,
                ScanIndexForward=False,
            )
        except Exception as e:
            print(f"[TicketClose] Failed DB query: {e}")
            await interaction.response.send_message(
                "Could not validate this ticket right now. Please try again.",
                ephemeral=True,
            )
            return

        items = query_response.get("Items", [])
        if not items:
            await interaction.response.send_message(
                "You can't use `/close` in this channel.", ephemeral=True
            )
            return

        ticket_item = items[0]
        private_channel_id = int(ticket_item.get("privateChannelId"))

        if private_channel_id != channel.id:
            await interaction.response.send_message(
                "You can't use `/close` in this channel.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            (
                "Are you sure you want to close this ticket?\n"
                "Closing this ticket will permanently delete this channel."
            ),
            view=TicketCloseConfirmView(ticket=ticket_item),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    """Load the TestCog."""
    await bot.add_cog(TicketCog(bot))
