"""
Ticket cog for BizBot.

Provides commands for ticket functionality
"""

import re
from datetime import datetime, timezone

import discord
from boto3.dynamodb.types import TypeDeserializer
from discord import app_commands
from discord.ext import commands

from lib.constants import TICKETS_TABLE
from lib.db import db
from services.discord.constants.temp_discord_roles import (
    PROD_GUILD_ID,
    PROD_TICKETS_CATEGORY_ID,
)

from .ticketCategoryView import TicketCategoryView
from .ticketCloseConfirmView import TicketCloseConfirmView

type_deserializer = TypeDeserializer()


def _in_allowed_ticket_category(
    guild: discord.Guild | None, category: discord.CategoryChannel | None
) -> bool:
    if guild is None or guild.id != PROD_GUILD_ID:
        return True
    return category is not None and category.id == PROD_TICKETS_CATEGORY_ID


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
        if not _in_allowed_ticket_category(interaction.guild, category):
            await interaction.response.send_message(
                "Please use `/ticket` in the designated tickets category.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild.id if interaction.guild else None
        await interaction.response.send_message(
            "Select the type of help you need:",
            view=TicketCategoryView(guild_id=guild_id),
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
        if not _in_allowed_ticket_category(interaction.guild, category):
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
        # TODO: CHANGE SORT KEY IN THE FUTURE
        event_year_key = f"{category_name};{datetime.now(timezone.utc).year}"

        # validate ticket_id and eventID;year against db
        try:
            ticket_item = await db.get_one_custom(
                params={
                    "TableName": f"{TICKETS_TABLE}{db.environment}",
                    "Key": {
                        "ticketID": {"S": ticket_id},
                        "eventID;year": {"S": event_year_key},
                    },
                }
            )
        except Exception as e:
            print(f"[TicketClose] Failed DB query: {e}")
            await interaction.response.send_message(
                "Could not validate this ticket right now. Please try again.",
                ephemeral=True,
            )
            return

        if ticket_item is None:
            await interaction.response.send_message(
                "You can't use `/close` in this channel.", ephemeral=True
            )
            return

        ticket_item = {
            key: type_deserializer.deserialize(value)
            for key, value in ticket_item.items()
        }

        private_channel_id = int(ticket_item["privateChannelId"])

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
