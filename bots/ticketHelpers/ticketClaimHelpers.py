import discord


def member_has_any_role(member: discord.Member, role_ids: list[int]) -> bool:
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
    message: discord.Message, claimer_mention: str, ticket_id: str
) -> None:
    if message.embeds:
        updated_embed = discord.Embed.from_dict(message.embeds[0].to_dict())
    else:
        updated_embed = discord.Embed(title=f"Ticket #{ticket_id[:8]}")

    updated_embed.color = discord.Color.blue()
    status_text = f"CLAIMED by {claimer_mention}"
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


async def create_private_ticket_channel(
    guild: discord.Guild,
    ticket_id: str,
    claimed_by: discord.Member,
    created_by: discord.Member | None,
    exec_roles: list[discord.Role],
    category: discord.CategoryChannel | None,
) -> discord.TextChannel:
    overwrites: dict[
        discord.Role | discord.Member | discord.Object,
        discord.PermissionOverwrite,
    ] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
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
