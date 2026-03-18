from datetime import datetime, timezone

import discord

from botocore.exceptions import ClientError
from lib.constants import TICKETS_TABLE
from lib.db import db
from .ticketClaimHelpers import (
    create_private_ticket_channel,
    get_ticket_id,
    member_has_any_role,
    resolve_member,
    roles_from_ids,
    set_ticket_message_claimed,
)

# Hard-coded for now;
MENTOR_ROLE_TO_ID_DICTIONARY = {
    "frontend": 1482999081302364161,
    "backend": 1482999306196750449,
    "product": 1482999350266298438,
    "UX": 1482998230013841521,
}

EXEC_ROLE_IDS = [
    1404646631688896604,  # Biztech Server
    1396397591465300098,  # Biztech test Server
    1423137037518770199,
]

MENTOR_ROLE_IDS = []

CLAIM_ALLOWED_ROLE_IDS = list({*EXEC_ROLE_IDS, *MENTOR_ROLE_IDS})


class ClaimTicketView(discord.ui.View):
    def __init__(self, ticket_id: str, event_year_key: str) -> None:
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.event_year_key = event_year_key

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            if value is None:
                return None
            return int(str(value))
        except (TypeError, ValueError):
            return None

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary)
    async def claim_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Claims can only be handled inside a server.",
                ephemeral=True,
            )
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Could not validate your server roles.",
                ephemeral=True,
            )
            return

        if not member_has_any_role(interaction.user, CLAIM_ALLOWED_ROLE_IDS):
            await interaction.response.send_message(
                "You do not have permission to claim tickets.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        claimed_at = datetime.now(timezone.utc).isoformat()

        try:
            update_response = await db.update_db(
                key={
                    "ticketID": self.ticket_id,
                    "eventID;year": self.event_year_key,
                },
                table=TICKETS_TABLE,
                update_expression=(
                    "SET #status = :claimed, "
                    "claimedBy = :claimedBy, "
                    "claimedAt = :claimedAt"
                ),
                expression_attribute_names={"#status": "status"},
                expression_attribute_values={
                    ":open": "OPEN",
                    ":claimed": "CLAIMED",
                    ":claimedBy": str(interaction.user.id),
                    ":claimedAt": claimed_at,
                },
                condition_expression="#status = :open",
                return_values="ALL_NEW",
            )
        except ClientError as err:
            print(f"[ClaimTicket] ClientError: {err}")
            error_code = err.response.get("Error", {}).get("Code")
            if error_code == "ConditionalCheckFailedException":
                await interaction.followup.send(
                    "Ticket is already claimed",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "Could not claim ticket due to a DB error.",
                    ephemeral=True,
                )
            return
        except Exception as e:
            print(f"[ClaimTicket] Exception during DB update: {e}")
            await interaction.followup.send(
                "Could not claim ticket due to an unexpected error.",
                ephemeral=True,
            )
            return

        ticket = update_response.get("Attributes", {})

        created_by_id = self._safe_int(ticket.get("createdBy"))

        if (
            not isinstance(interaction.channel, discord.TextChannel)
            or interaction.message is None
        ):
            await interaction.followup.send(
                "Could not resolve the original ticket message.",
                ephemeral=True,
            )
            return

        queue_channel = interaction.channel
        queue_message = interaction.message

        try:
            await set_ticket_message_claimed(
                message=queue_message,
                claimer_mention=interaction.user.mention,
                ticket_id=self.ticket_id,
            )
        except discord.HTTPException as e:
            print(f"[ClaimTicket] Failed to update ticket message: {e}")

        # create private channel
        created_by_member = await resolve_member(guild, created_by_id)

        exec_roles = roles_from_ids(guild, EXEC_ROLE_IDS)

        # Get bot member for channel permissions
        bot_member = guild.me
        if bot_member is None:
            await interaction.followup.send(
                "Could not resolve bot permissions.",
                ephemeral=True,
            )
            return

        try:
            private_ticket_channel = await create_private_ticket_channel(
                guild=guild,
                ticket_id=self.ticket_id,
                claimed_by=interaction.user,
                created_by=created_by_member,
                exec_roles=exec_roles,
                category=queue_channel.category,
                bot_member=bot_member,
            )
        except discord.HTTPException as e:
            print(f"[ClaimTicket] Failed to create private channel: {e}")
            await interaction.followup.send(
                "Ticket claimed, but failed to create private channel.",
                ephemeral=True,
            )
            return

        try:
            await db.update_db(
                key={
                    "ticketID": self.ticket_id,
                    "eventID;year": self.event_year_key,
                },
                table=TICKETS_TABLE,
                obj={"privateChannelId": str(private_ticket_channel.id)},
            )
        except Exception as e:
            print(f"[ClaimTicket] Failed to save private channel ID: {e}")

        mentions = [interaction.user.mention]
        if created_by_member is not None:
            mentions.append(created_by_member.mention)
        elif created_by_id is not None:
            mentions.append(f"<@{created_by_id}>")

        await private_ticket_channel.send(
            " ".join(mentions) + "\nTicket claimed. Continue discussion here."
        )

        await interaction.followup.send(
            f"Ticket claimed. Private channel created: {private_ticket_channel.mention}",
            ephemeral=True,
        )


class TicketCreateModal(discord.ui.Modal):
    description = discord.ui.TextInput(
        label="Describe what you need help with",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
        placeholder="Briefly explain your issue ...",
    )

    location = discord.ui.TextInput(
        label="Where are you located?",
        style=discord.TextStyle.short,
        max_length=100,
        required=True,
        placeholder="Henry Angus 491 / etc.",
    )

    def __init__(self, selected_help_category: str):
        super().__init__(title="Create Ticket")
        # Pass data from category dropdown
        self.selected_help_category = selected_help_category

    async def on_submit(self, interaction: discord.Interaction) -> None:
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
                "Please create tickets from a server text channel under an event category.",
                ephemeral=True,
            )
            return

        event_id = str(category.id)
        event_name = category.name

        now_utc = datetime.now(timezone.utc)
        now = now_utc.isoformat()

        ticket_id = 0
        try:
            ticket_id = await get_ticket_id(event_name, now_utc.year)
        except Exception as e:
            print(e)
            await interaction.response.send_message(
                "Unable to read ticket counter for this event.", ephemeral=True
            )
            return


        event_year_key = f"{event_name};{now_utc.year}"

        tickets_channel = discord.utils.get(
            category.text_channels, name="incoming-tickets"
        )

        if not isinstance(tickets_channel, discord.TextChannel):
            await interaction.response.send_message(
                "Tickets channel is not configured correctly.", ephemeral=True
            )
            return

        # Queue message into mentor chat
        ticket_title = f"Ticket #{ticket_id}"
        embed = discord.Embed(title=ticket_title, color=discord.Color.red())
        embed.add_field(name="Created By", value=interaction.user.mention, inline=True)
        embed.add_field(
            name="Help Category", value=self.selected_help_category, inline=True
        )
        embed.add_field(
            name="Where are you located", value=self.location.value, inline=False
        )
        embed.add_field(name="Description", value=self.description.value, inline=False)
        embed.add_field(name="Status", value="OPEN", inline=False)

        claim_view = ClaimTicketView(ticket_id=str(ticket_id), event_year_key=event_year_key)

        mentor_ping = f"<@&{MENTOR_ROLE_TO_ID_DICTIONARY[self.selected_help_category]}>"
        try:
            queue_message = await tickets_channel.send(
                content=f"{mentor_ping} New ticket needs help.",
                embed=embed,
                view=claim_view,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "Error posting to the mentor channel failed.",
                ephemeral=True,
            )
            return

        ticket_item = {
            "ticketID": str(ticket_id),
            "eventID;year": event_year_key,
            "eventId": event_id,
            "eventName": event_name,
            "createdBy": str(interaction.user.id),
            "helpCategory": self.selected_help_category,
            "description": self.description.value,
            "location": self.location.value,
            "status": "OPEN",
            "queueChannelId": str(tickets_channel.id),
            "queueMessageId": str(queue_message.id),
            "createdAt": now,
        }

        try:
            await db.create(ticket_item, TICKETS_TABLE)
        except Exception:
            try:
                await queue_message.delete()
            except discord.HTTPException:
                pass

            await interaction.response.send_message(
                "Ticket could not be saved to DB, so the mentor message was removed.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Your ticket has been created. Ticket ID: `{ticket_id}`",
            ephemeral=True,
        )
