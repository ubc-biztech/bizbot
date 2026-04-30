"""
Ticket cog for BizBot.

Provides commands for ticket functionality
"""

import re

import discord
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from discord import app_commands
from discord.ext import commands

from lib.constants import TICKETS_TABLE
from lib.db import db
from services.discord.constants.temp_discord_roles import (
    EXEC_ROLE_IDS,
)

from .adjustRolesView import AdjustRolesView
from .discordEventsStore import (
    create_event,
    get_discord_events_table_name,
    is_event_active,
    resolve_category_from_channel,
    stop_event,
)
from .discordRolesStore import (
    get_discord_roles_table_name,
    list_configured_roles_in_guild,
)
from .ticketCategoryView import TicketCategoryView
from .ticketCloseConfirmView import TicketCloseConfirmView

type_deserializer = TypeDeserializer()


def _member_has_exec_role(member: discord.Member) -> bool:
    member_role_ids = {role.id for role in member.roles}
    return any(role_id in member_role_ids for role_id in EXEC_ROLE_IDS)


class TicketCog(commands.Cog):
    """Ticket commands for BizBot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show BizBot ticket command help")
    async def help(self, interaction: discord.Interaction):
        help_text = (
            "**BizBot Ticket Commands**\n"
            "`/createevent` - Set up this category for ticketing. "
            "Creates missing channels: ticket-help, "
            "ticket-log, incoming-tickets. "
            "(Exec roles only)\n"
            "`/stopevent` - Stop new `/ticket` creation in this category. "
            "Existing tickets can still be claimed and closed. (Exec roles only)\n"
            "`/adjustroles` - Add/remove roles that can be pinged for help in tickets. "
            "Roles must already exist in this Discord server. (Exec roles only)\n"
            "`/ticket` - Create a new help ticket.\n"
            "`/close` - Close the current ticket. Use in a private ticket channel."
        )
        await interaction.response.send_message(help_text, ephemeral=True)

    @app_commands.command(name="ticket", description="Create a help ticket")
    async def ticket(self, interaction: discord.Interaction):
        """/ticket command to create a ticket"""
        category = resolve_category_from_channel(interaction.channel)

        if category is None:
            await interaction.response.send_message(
                "Please use `/ticket` inside an event category.", ephemeral=True
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
            event_is_active = await is_event_active(guild.id, category.id)
        except ClientError as err:
            error_code = err.response.get("Error", {}).get("Code")
            if error_code == "ResourceNotFoundException":
                table_name = get_discord_events_table_name(guild.id)
                await interaction.response.send_message(
                    (
                        f"Event configuration table `{table_name}` was not found. "
                        "Please create it first."
                    ),
                    ephemeral=True,
                )
                return
            raise

        if not event_is_active:
            await interaction.response.send_message(
                "Ticketing is not active for this category.",
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
        name="createevent",
        description="Enable ticketing in this category",
    )
    @app_commands.guild_only()
    async def createevent(self, interaction: discord.Interaction):
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

        category = resolve_category_from_channel(interaction.channel)
        if category is None:
            await interaction.response.send_message(
                "Run this command in a text channel under the event category.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        required_channels = ("ticket-help", "ticket-log", "incoming-tickets")
        existing_channel_names = {
            text_channel.name for text_channel in category.text_channels
        }
        created_channels: list[str] = []

        for channel_name in required_channels:
            if channel_name in existing_channel_names:
                continue
            try:
                await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    reason=(
                        f"Event setup by {interaction.user} ({interaction.user.id}) "
                        "for ticketing workflow"
                    ),
                )
                created_channels.append(channel_name)
            except discord.HTTPException as e:
                print(f"[CreateEvent] Failed to create channel {channel_name}: {e}")
                await interaction.followup.send(
                    f"Failed to create required channel `{channel_name}`.",
                    ephemeral=True,
                )
                return

        try:
            created_new_event = await create_event(guild.id, category.id)
        except ClientError as err:
            error_code = err.response.get("Error", {}).get("Code")
            if error_code == "ResourceNotFoundException":
                table_name = get_discord_events_table_name(guild.id)
                await interaction.followup.send(
                    (
                        f"Event configuration table `{table_name}` was not found. "
                        "Please create it first."
                    ),
                    ephemeral=True,
                )
                return
            raise

        channels_message = (
            "Created channel(s): "
            f"{', '.join(f'`{name}`' for name in created_channels)}."
            if created_channels
            else "All required channels already existed."
        )
        event_message = (
            "Event activated for ticketing."
            if created_new_event
            else "Event was already active for ticketing."
        )

        await interaction.followup.send(
            f"{event_message} {channels_message}",
            ephemeral=True,
        )

    @app_commands.command(
        name="stopevent",
        description="Disable ticketing in this category",
    )
    @app_commands.guild_only()
    async def stopevent(self, interaction: discord.Interaction):
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

        category = resolve_category_from_channel(interaction.channel)
        if category is None:
            await interaction.response.send_message(
                "Run this command in a text channel under the event category.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            removed = await stop_event(guild.id, category.id)
        except ClientError as err:
            error_code = err.response.get("Error", {}).get("Code")
            if error_code == "ResourceNotFoundException":
                table_name = get_discord_events_table_name(guild.id)
                await interaction.followup.send(
                    (
                        f"Event configuration table `{table_name}` was not found. "
                        "Please create it first."
                    ),
                    ephemeral=True,
                )
                return
            raise

        if removed:
            await interaction.followup.send(
                "Event stopped. `/ticket` is now disabled for this category.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "This category was not active in the event table.",
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

        channel_match = re.fullmatch(r"ticket-(\d+)", channel.name)
        if channel_match is None:
            await interaction.response.send_message(
                "You can't use `/close` in this channel.", ephemeral=True
            )
            return

        ticket_id = channel_match.group(1)
        category_name = category.name
        event_year_key = f"{category_name}"

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
