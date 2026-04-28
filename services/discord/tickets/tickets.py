"""
Ticket cog for BizBot.

Provides commands for ticket functionality
"""

import re
from datetime import datetime, timezone

import discord
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from discord import app_commands
from discord.ext import commands

from lib.constants import TICKETS_TABLE
from lib.db import db
from services.discord.constants.temp_discord_roles import (
    EXEC_ROLE_IDS,
    PROD_GUILD_ID,
    PROD_TICKETS_CATEGORY_ID,
)

from .adjustRolesView import AdjustRolesView
from .discordRolesStore import (
    get_discord_roles_table_name,
    list_configured_roles_in_guild,
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


def _member_has_exec_role(member: discord.Member) -> bool:
    member_role_ids = {role.id for role in member.roles}
    return any(role_id in member_role_ids for role_id in EXEC_ROLE_IDS)


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

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Tickets can only be created inside a server.",
                ephemeral=True,
            )
            return

        try:
            configured_roles = await list_configured_roles_in_guild(guild)
        except ClientError as err:
            error_code = err.response.get("Error", {}).get("Code")
            if error_code == "ResourceNotFoundException":
                table_name = get_discord_roles_table_name(guild.id)
                await interaction.response.send_message(
                    (
                        f"Role configuration table `{table_name}` was not found. "
                        "Please create it first."
                    ),
                    ephemeral=True,
                )
                return
            raise

        if not configured_roles:
            await interaction.response.send_message(
                (
                    "No ticket-ping roles are configured. "
                    "Ask an admin to run `/adjustroles`."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Select the type of help you need:",
            view=TicketCategoryView(roles=configured_roles[:25]),
            ephemeral=True,
        )

    @app_commands.command(
        name="adjustroles",
        description="Add or remove ticket-ping roles from DB configuration",
    )
    @app_commands.guild_only()
    async def adjustroles(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Could not validate your server permissions.",
                ephemeral=True,
            )
            return

        if not _member_has_exec_role(interaction.user):
            await interaction.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command only works inside a server.",
                ephemeral=True,
            )
            return

        table_name = get_discord_roles_table_name(guild.id)
        try:
            configured_roles = await list_configured_roles_in_guild(guild)
        except ClientError as err:
            error_code = err.response.get("Error", {}).get("Code")
            if error_code == "ResourceNotFoundException":
                await interaction.response.send_message(
                    (
                        f"Role configuration table `{table_name}` was not found. "
                        "Please create it first."
                    ),
                    ephemeral=True,
                )
                return
            raise

        if configured_roles:
            role_lines = "\n".join(role.mention for role in configured_roles)
        else:
            role_lines = "_No roles configured yet._"

        view = AdjustRolesView(guild=guild)
        await interaction.response.send_message(
            (
                f"Editing ticket-ping roles in `{table_name}`.\n"
                "Select roles below, then use Add/Remove.\n\n"
                f"Current roles:\n{role_lines}"
            ),
            view=view,
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
