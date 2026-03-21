import discord

from lib.constants import TICKET_EVENTS_TABLE
from lib.db import db

        
async def newEvent(
        event_name: str,
        year: int,
        role: discord.Role,
        mentor_role: discord.Role,
        submit_channel: discord.TextChannel,
        claim_channel: discord.TextChannel,
        interaction: discord.Interaction
    ):

    event_year_key = f"{event_name};{year}"

    event_item = {
            "eventID;year": event_year_key,
            "eventID": event_name,
            "eventRoleID": role.id,
            "mentorRoleID": mentor_role.id,
            "submitChannelID": submit_channel.id,
            "claimChannelID": claim_channel.id
        }

    try:
        await db.create(event_item, TICKET_EVENTS_TABLE)
    except Exception as e:
        print("Event couldn't be saved", e)
        await interaction.response.send_message(
            "Event could not be saved into DB",
            ephemeral=True
        )
        return;

    

