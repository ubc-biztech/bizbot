from datetime import datetime, timezone
from decimal import Decimal

import discord
from botocore.exceptions import ClientError

from lib.constants import TICKETS_TABLE
from lib.db import db
from services.discord.constants.temp_discord_roles import (
    CLAIM_ALLOWED_ROLE_IDS,
    EXEC_ROLE_IDS,
)

from .ticketClaimHelpers import (
    create_private_ticket_channel,
    get_ticket_id,
    member_has_any_role,
    resolve_member,
    set_ticket_message_claimed,
)


class ClaimTicketView(discord.ui.View):
    def __init__(self, ticket_id: str, event_year_key: str) -> None:
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.event_year_key = event_year_key

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

        claimed_at_epoch = int(datetime.now(timezone.utc).timestamp() * 1000)

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
                    ":claimedBy": interaction.user.id,
                    ":claimedAt": claimed_at_epoch,
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

        # db.update_db() returns attributes directly, not a DynamoDB response envelope.
        ticket = update_response
        created_by_raw = ticket.get("createdBy")
        if isinstance(created_by_raw, Decimal):
            created_by_id = int(created_by_raw)
        elif isinstance(created_by_raw, int):
            created_by_id = created_by_raw
        else:
            try:
                created_by_id = int(str(created_by_raw))
            except (TypeError, ValueError):
                created_by_id = None

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
                claimer=interaction.user.mention,
                ticket_id=self.ticket_id,
            )
        except discord.HTTPException as e:
            print(f"[ClaimTicket] Failed to update ticket message: {e}")

        # create private channel
        created_by_member = await resolve_member(guild, created_by_id)

        exec_roles = [
            role
            for role_id in EXEC_ROLE_IDS
            if (role := guild.get_role(role_id)) is not None
        ]

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
                obj={"privateChannelId": private_ticket_channel.id},
            )
        except Exception as e:
            print(f"[ClaimTicket] Failed to save private channel ID: {e}")

        mentions: list[str] = []
        seen_mentions: set[str] = set()

        def append_unique_mention(mention: str | None) -> None:
            if mention is None or mention in seen_mentions:
                return
            seen_mentions.add(mention)
            mentions.append(mention)

        append_unique_mention(interaction.user.mention)
        if created_by_member is not None:
            append_unique_mention(created_by_member.mention)
        elif created_by_id is not None:
            append_unique_mention(f"<@{created_by_id}>")

        await private_ticket_channel.send(
            " ".join(mentions) + "\nTicket claimed. Continue discussion here."
        )

        await interaction.followup.send(
            f"Ticket claimed. Private channel created: "
            f"{private_ticket_channel.mention}",
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

    def __init__(self, selected_role_id: str):
        super().__init__(title="Create Ticket")
        # Pass selected ping role from dropdown
        self.selected_role_id = selected_role_id

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
                "Please create tickets from a server text channel "
                "under an event category.",
                ephemeral=True,
            )
            return

        event_id = str(category.id)
        event_name = category.name

        now_utc = datetime.now(timezone.utc)
        ticket_id = 0
        try:
            ticket_id = await get_ticket_id(event_name, now_utc.year)
        except Exception as e:
            print(e)
            await interaction.response.send_message(
                "Unable to read ticket counter for this event.", ephemeral=True
            )
            return

        created_at_epoch = int(now_utc.timestamp() * 1000)
        event_year_key = f"{event_name};{now_utc.year}"

        tickets_channel = discord.utils.get(
            category.text_channels, name="incoming-tickets"
        )

        if not isinstance(tickets_channel, discord.TextChannel):
            await interaction.response.send_message(
                "Tickets channel is not configured correctly.", ephemeral=True
            )
            return

        guild = interaction.guild
        mentor_role_id: int | None = None
        try:
            mentor_role_id = int(self.selected_role_id)
        except ValueError:
            mentor_role_id = None

        mentor_role = (
            guild.get_role(mentor_role_id)
            if guild is not None and mentor_role_id is not None
            else None
        )
        if mentor_role is None:
            await interaction.response.send_message(
                "Selected role is no longer available. Please retry `/ticket`.",
                ephemeral=True,
            )
            return

        help_category_label = mentor_role.name

        # Queue message into mentor chat
        ticket_title = f"Ticket #{ticket_id}"
        embed = discord.Embed(title=ticket_title, color=discord.Color.red())
        embed.add_field(name="Created By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Help Category", value=help_category_label, inline=True)
        embed.add_field(
            name="Where are you located", value=self.location.value, inline=False
        )
        embed.add_field(name="Description", value=self.description.value, inline=False)
        embed.add_field(name="Status", value="OPEN", inline=False)

        claim_view = ClaimTicketView(
            ticket_id=str(ticket_id), event_year_key=event_year_key
        )

        mentor_ping = f"<@&{mentor_role_id}>"
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
            "createdBy": interaction.user.id,
            "helpCategory": help_category_label,
            "pingRoleId": mentor_role_id,
            "description": self.description.value,
            "location": self.location.value,
            "status": "OPEN",
            "queueChannelId": tickets_channel.id,
            "queueMessageId": queue_message.id,
            "createdAt": created_at_epoch,
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
