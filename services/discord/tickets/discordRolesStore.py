from collections.abc import Iterable

import discord
from botocore.exceptions import ClientError

from lib.db import db
from services.discord.constants.temp_discord_roles import PROD_GUILD_ID

TEST_DISCORD_ROLES_TABLE = "discordRoles"
PROD_DISCORD_ROLES_TABLE = "discordRolesPROD"


def get_discord_roles_table_name(guild_id: int | None) -> str:
    if guild_id == PROD_GUILD_ID:
        return PROD_DISCORD_ROLES_TABLE
    return TEST_DISCORD_ROLES_TABLE


def _coerce_role_id(raw_role_id: object) -> int | None:
    try:
        return int(str(raw_role_id))
    except (TypeError, ValueError):
        return None


async def list_configured_role_ids(guild_id: int | None) -> list[int]:
    table_name = get_discord_roles_table_name(guild_id)
    table = db.dynamodb.Table(table_name)  # type: ignore[attr-defined]

    role_ids: set[int] = set()
    last_evaluated_key = None

    while True:
        scan_kwargs: dict[str, object] = {"ProjectionExpression": "roleId"}
        if last_evaluated_key is not None:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = table.scan(**scan_kwargs)

        for item in response.get("Items", []):
            role_id = _coerce_role_id(item.get("roleId"))
            if role_id is not None:
                role_ids.add(role_id)

        last_evaluated_key = response.get("LastEvaluatedKey")
        if last_evaluated_key is None:
            break

    return sorted(role_ids)


async def add_configured_roles(guild_id: int | None, role_ids: Iterable[int]) -> int:
    table_name = get_discord_roles_table_name(guild_id)
    table = db.dynamodb.Table(table_name)  # type: ignore[attr-defined]

    added_count = 0
    for role_id in {int(role_id) for role_id in role_ids}:
        try:
            table.put_item(
                Item={"roleId": str(role_id)},
                ConditionExpression="attribute_not_exists(roleId)",
            )
            added_count += 1
        except ClientError as err:
            error_code = err.response.get("Error", {}).get("Code")
            if error_code != "ConditionalCheckFailedException":
                raise

    return added_count


async def remove_configured_roles(guild_id: int | None, role_ids: Iterable[int]) -> int:
    table_name = get_discord_roles_table_name(guild_id)
    table = db.dynamodb.Table(table_name)  # type: ignore[attr-defined]

    removed_count = 0
    for role_id in {int(role_id) for role_id in role_ids}:
        response = table.delete_item(
            Key={"roleId": str(role_id)},
            ReturnValues="ALL_OLD",
        )
        if response.get("Attributes"):
            removed_count += 1

    return removed_count


async def list_configured_roles_in_guild(guild: discord.Guild) -> list[discord.Role]:
    role_ids = await list_configured_role_ids(guild.id)
    roles: list[discord.Role] = []

    for role_id in role_ids:
        role = guild.get_role(role_id)
        if role is not None:
            roles.append(role)

    return sorted(roles, key=lambda role: role.name.lower())


async def cleanup_deleted_roles_from_config(guild: discord.Guild) -> None:
    configured_role_ids = await list_configured_role_ids(guild.id)
    existing_role_ids = {role.id for role in guild.roles}

    stale_role_ids = [
        role_id for role_id in configured_role_ids if role_id not in existing_role_ids
    ]
    if not stale_role_ids:
        return

    await remove_configured_roles(guild.id, stale_role_ids)
