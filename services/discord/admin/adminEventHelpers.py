import discord

from lib.constants import TICKET_EVENTS_TABLE
from lib.db import db

        
async def newEvent(
        event_name: str,
        year: int,
        role: discord.Role,
        mentor_role: discord.Role,
        submit_channel: discord.TextChannel,
        claim_channel: discord.TextChannel
    ):

    event_year_key = f"{event_name};{year}"

    event_item = {
            "eventId;year": event_year_key,
            "eventId": event_name,
            "eventRoleId": role.id,
            "mentorRoleId": role.id,
            "submitChannelId": submit_channel.id,
            "claimChannelId": claim_channel.id
        }

    try:
        await db.create(event_item, TICKET_EVENTS_TABLE)
    except Exception:
        print("Event couldn't be saved")

    

