"""
FastAPI application for BizBot.

Provides HTTP endpoints for health checks and testing DynamoDB connectivity.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from lib.constants import TICKETS_TABLE
from lib.db import db
from services.discord.client import bot

app = FastAPI(
    title="BizBot API",
    description="Internal API for BizBot Discord bot",
    version="0.1.0",
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"service": "BizBot API", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns bot connection status and service health.
    Useful for monitoring, load balancers, and deployment verification.
    """
    bot_ready = bot.is_ready() if bot else False
    bot_user = str(bot.user) if bot and bot.user else "Not connected"

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "bot_connected": bot_ready,
            "bot_user": bot_user,
            "guild_count": len(bot.guilds) if bot_ready else 0,
        },
    )


@app.get("/test-db/item/{item_id}")
async def get_test_item(item_id: str):
    """
    Get a specific item from DynamoDB.

    Modify the key structure based on your table's schema.
    Example: /test-db/item/test-123
    """
    try:
        # Modify this key structure to match your table's primary key
        item = await db.get_one(item_id, TICKETS_TABLE)

        if item:
            return {"status": "success", "item": item}
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "not_found",
                    "message": f"Item with ticket_id '{item_id}' not found",
                },
            )
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )
