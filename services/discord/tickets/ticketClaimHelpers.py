import discord

from lib.constants import COUNTER_KEY, TICKETS_TABLE, TICKET_EVENTS_TABLE
from lib.db import db


async def get_claim_channel_id(eventID: str, year: int) -> int | None:
    """Checks biztechTicketsEvents table for event's claim channelID"""
    try:
        event_item = await db.get_one_custom({
            "TableName": TICKET_EVENTS_TABLE,
            "Key": {
                "eventID": {"S": eventID},
                "eventID;year": {"S": f"{eventID};{year}"}
                }
        })

        if (event_item is not None):
            return int(event_item["claimChannelID"]["N"])
        else:
            return None;
        
    except Exception as e:
        print("DB Error", e)
        return None

def member_has_any_role(member: discord.Member, role_ids: set[int]) -> bool:
    """Return True if member has at least one role from role_ids."""
    member_role_ids = {role.id for role in member.roles}
    return any(role_id in member_role_ids for role_id in role_ids)


def roles_from_ids(guild: discord.Guild, role_ids: list[int]) -> list[discord.Role]:
    roles: list[discord.Role] = []
    seen: set[int] = set()
    for role_id in role_ids:
        if role_id in seen:
            continue
        seen.add(role_id)
        role = guild.get_role(role_id)
        if role is not None:
            roles.append(role)
    return roles


async def resolve_member(
    guild: discord.Guild, member_id: int | None
) -> discord.Member | None:
    """Resolve a guild member by ID via cache first, then API fallback."""
    if member_id is None:
        return None

    member = guild.get_member(member_id)
    if member is not None:
        return member

    try:
        return await guild.fetch_member(member_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


async def set_ticket_message_claimed(
    message: discord.Message, claimer: str, ticket_id: str
) -> None:
    """Set ticket embed status to claimed and remove interactive view."""
    if not message.embeds:
        return
    updated_embed = discord.Embed.from_dict(message.embeds[0].to_dict())

    updated_embed.color = discord.Color.blue()
    status_text = f"CLAIMED by {claimer}"
    status_updated = False

    for idx, field in enumerate(updated_embed.fields):
        if field.name == "Status":
            updated_embed.set_field_at(
                idx,
                name="Status",
                value=status_text,
                inline=field.inline,
            )
            status_updated = True
            break

    if not status_updated:
        updated_embed.add_field(name="Status", value=status_text, inline=False)

    await message.edit(embed=updated_embed, view=None)


async def get_ticket_id(eventID, year) -> int:
    item = await db.update_db(
        key={"ticketID": COUNTER_KEY, "eventID;year": f"{eventID};{year}"},
        table=TICKETS_TABLE,
        update_expression=("ADD #counter :inc"),
        expression_attribute_names={"#counter": "counter"},
        expression_attribute_values={
            ":inc": 1,
        },
        return_values="UPDATED_NEW",
    )

    return item["counter"]


async def create_private_ticket_channel(
    guild: discord.Guild,
    ticket_id: str,
    claimed_by: discord.Member,
    created_by: discord.Member | None,
    exec_roles: list[discord.Role],
    category: discord.CategoryChannel | None,
    bot_member: discord.Member,
) -> discord.TextChannel:
    """
    Create a private channel for a claimed ticket.

    Permission model:
    - @everyone: hidden (view_channel=False)
    - Bot: can view and send messages
    - Participants (claimer, ticket creator): can view and send messages
    - Exec roles: same as participants + manage_messages

    The channel is created under the same category as the ticket queue.
    """
    overwrites: dict[
        discord.Role | discord.Member | discord.Object,
        discord.PermissionOverwrite,
    ] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        bot_member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
        claimed_by: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
    }

    if created_by is not None:
        overwrites[created_by] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        )

    for exec_role in exec_roles:
        overwrites[exec_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
        )

    return await guild.create_text_channel(
        name=f"ticket-{ticket_id[:8]}",
        category=category,
        overwrites=overwrites,
        reason=f"Ticket claimed by {claimed_by} ({claimed_by.id})",
    )
