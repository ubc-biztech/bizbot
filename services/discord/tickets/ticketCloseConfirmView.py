from datetime import datetime, timezone
from typing import Any

import discord

from lib.constants import TICKETS_TABLE
from lib.db import db

from .ticketClaimHelpers import set_ticket_message_closed


def _format_duration_ms(duration_ms: int) -> str:
    total_seconds = duration_ms // 1000
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self, ticket: dict[str, Any]):
        super().__init__(timeout=90)
        self.ticket = ticket

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        _ = button

        # Guard in case channel doesn't exist anymore
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Could not resolve the current channel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        ticket_id = str(self.ticket["ticketID"])
        event_year_key = str(self.ticket["eventID;year"])
        closed_at_epoch = int(datetime.now(timezone.utc).timestamp() * 1000)

        queue_channel_id = int(self.ticket["queueChannelId"])
        queue_message_id = int(self.ticket["queueMessageId"])

        queue_channel = interaction.client.get_channel(queue_channel_id)

        if queue_channel is None:
            try:
                queue_channel = await interaction.client.fetch_channel(queue_channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                queue_channel = None

        if not isinstance(queue_channel, discord.TextChannel):
            await interaction.followup.send(
                "Could not resolve the incoming-tickets channel for this ticket.",
                ephemeral=True,
            )
            return

        try:
            queue_message = await queue_channel.fetch_message(queue_message_id)
            await set_ticket_message_closed(
                message=queue_message,
                closer=interaction.user.mention,
            )
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
            print(f"[TicketClose] Failed to update queue message: {e}")
            await interaction.followup.send(
                "Could not update the ticket message.",
                ephemeral=True,
            )
            return

        category = getattr(channel, "category", None)
        log_channel = (
            discord.utils.get(category.text_channels, name="ticket-log")
            if isinstance(category, discord.CategoryChannel)
            else None
        )

        await interaction.followup.send(
            "Closing ticket and deleting this channel...",
            ephemeral=True,
        )

        # Delete channel
        try:
            await channel.delete(
                reason=(
                    f"Ticket {ticket_id} closed by "
                    f"{interaction.user} ({interaction.user.id})"
                )
            )
        except discord.HTTPException as e:
            print(f"[TicketClose] Failed to delete private channel: {e}")
            await interaction.followup.send(
                "Failed to delete this ticket channel.",
                ephemeral=True,
            )
            return

        # Log in #ticket-log
        created_at = int(self.ticket["createdAt"])
        claimed_at = int(self.ticket["claimedAt"])
        claimed_by_id = int(self.ticket["claimedBy"])
        closed_at_seconds = closed_at_epoch // 1000

        wait_until_claimed_ms = claimed_at - created_at
        claimed_to_closed_ms = closed_at_epoch - claimed_at

        if isinstance(log_channel, discord.TextChannel):
            log_embed = discord.Embed(
                title=f"Ticket #{ticket_id} Closed",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )
            log_embed.add_field(name="Requested By", value=interaction.user.mention)
            log_embed.add_field(
                name="Claimed By",
                value=f"<@{claimed_by_id}>",
            )
            log_embed.add_field(
                name="Waited Until Claimed",
                value=_format_duration_ms(wait_until_claimed_ms),
                inline=False,
            )
            log_embed.add_field(
                name="Claimed To Closed",
                value=_format_duration_ms(claimed_to_closed_ms),
                inline=False,
            )
            log_embed.add_field(
                name="Closed At",
                value=f"<t:{closed_at_seconds}:F>",
                inline=False,
            )
            try:
                await log_channel.send(embed=log_embed)
            except discord.HTTPException as e:
                print(f"[TicketClose] Failed to log in ticket-log: {e}")

        # Update DB
        try:
            await db.update_db(
                key={"ticketID": ticket_id, "eventID;year": event_year_key},
                table=TICKETS_TABLE,
                obj={"status": "CLOSED", "closedAt": closed_at_epoch},
            )
        except Exception as e:
            print(f"[TicketClose] Failed to update DB status: {e}")
