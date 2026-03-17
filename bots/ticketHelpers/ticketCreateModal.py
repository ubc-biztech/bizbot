import uuid
from datetime import datetime, timezone

import discord
from bots.constants import TICKETS_TABLE
from bots.db import db

# Hard-coded for now;
MENTOR_ROLE_TO_ID_DICTIONARY = {
    "frontend" : 1482999081302364161,
    "backend" : 1482999306196750449,
    "product" : 1482999350266298438,
    "UX" : 1482998230013841521
}


# Stub
class ClaimTicketView(discord.ui.View):
    def __init__(self, ticket_id: str, event_id: str) -> None:
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.event_id = event_id

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary)
    async def claim_ticket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            f"Ticket `{self.ticket_id[:8]}` TODO.",
            ephemeral=True,
        )


class TicketCreateModal(discord.ui.Modal):
    description = discord.ui.TextInput(
        label="Describe what you need help with",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
        placeholder="Briefly explain your issue ..."
    )

    location = discord.ui.TextInput(
        label="Where are you located?",
        style=discord.TextStyle.short,
        max_length=100,
        required=True,
        placeholder="Henry Angus 491 / etc."
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
                ephemeral=True
            )
            return

        event_id = str(category.id)
        event_name = category.name

        ticket_id = str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc)
        now = now_utc.isoformat()
        event_year_key = f"{event_name};{now_utc.year}"

        tickets_channel = discord.utils.get(category.text_channels, name="incoming-tickets")

        if not isinstance(tickets_channel, discord.TextChannel):
            await interaction.response.send_message(
                "Tickets channel is not configured correctly.",
                ephemeral=True
            )
            return
        
        # Queue message into mentor chat
        ticket_title = "Ticket #" + ticket_id[:8]
        embed = discord.Embed(title=ticket_title, color=discord.Color.red())
        embed.add_field(name="Created By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Help Category", value=self.selected_help_category, inline=True)
        embed.add_field(name="Where are you located", value=self.location.value, inline=False)
        embed.add_field(name="Description", value=self.description.value, inline=False)
        embed.add_field(name="Status", value="OPEN", inline=False)

        claim_view = ClaimTicketView(ticket_id=ticket_id, event_id=event_id)

        mentor_ping = f"<@&{MENTOR_ROLE_TO_ID_DICTIONARY[self.selected_help_category]}>"
        try:
            queue_message = await tickets_channel.send(
                content=f"{mentor_ping} New ticket needs help.",
                embed=embed,
                view=claim_view
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "Error posting to the mentor channel failed.",
                ephemeral=True,
            )
            return

        ticket_item = {
            "id": ticket_id,
            "ticketID": ticket_id,
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
            f"Your ticket has been created. Ticket ID: `{ticket_id[:8]}`",
            ephemeral=True
        )
