import discord
from botocore.exceptions import ClientError

from lib.db import db
from services.discord.constants.temp_discord_roles import PROD_GUILD_ID

TEST_DISCORD_EVENTS_TABLE = "discordEvents"
PROD_DISCORD_EVENTS_TABLE = "discordEventsPROD"


def get_discord_events_table_name(guild_id: int | None) -> str:
    if guild_id == PROD_GUILD_ID:
        return PROD_DISCORD_EVENTS_TABLE
    return TEST_DISCORD_EVENTS_TABLE


async def is_event_active(guild_id: int | None, category_id: int) -> bool:
    table_name = get_discord_events_table_name(guild_id)
    table = db.dynamodb.Table(table_name)  # type: ignore[attr-defined]
    response = table.get_item(Key={"categoryID": str(category_id)})
    return "Item" in response


async def create_event(guild_id: int | None, category_id: int) -> bool:
    table_name = get_discord_events_table_name(guild_id)
    table = db.dynamodb.Table(table_name)  # type: ignore[attr-defined]

    try:
        table.put_item(
            Item={"categoryID": str(category_id)},
            ConditionExpression="attribute_not_exists(categoryID)",
        )
        return True
    except ClientError as err:
        error_code = err.response.get("Error", {}).get("Code")
        if error_code == "ConditionalCheckFailedException":
            return False
        raise


async def stop_event(guild_id: int | None, category_id: int) -> bool:
    table_name = get_discord_events_table_name(guild_id)
    table = db.dynamodb.Table(table_name)  # type: ignore[attr-defined]

    response = table.delete_item(
        Key={"categoryID": str(category_id)},
        ReturnValues="ALL_OLD",
    )
    return "Attributes" in response


def resolve_category_from_channel(
    channel: discord.abc.GuildChannel | discord.Thread | None,
) -> discord.CategoryChannel | None:
    if isinstance(channel, discord.TextChannel):
        return channel.category
    if isinstance(channel, discord.Thread) and isinstance(
        channel.parent, discord.TextChannel
    ):
        return channel.parent.category
    return None
