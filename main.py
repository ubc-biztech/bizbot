"""
BizBot - Discord bot for BizTech event support

Main entry point that runs both the Discord bot and FastAPI server concurrently.
"""

import asyncio
import uvicorn

from dotenv import load_dotenv
from bots.client import start_bot, stop_bot
from api.routes import app


async def run_fastapi():
    """Run FastAPI server using uvicorn."""
    config = uvicorn.Config(
        app=app, host="0.0.0.0", port=8000, log_level="info", access_log=True
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """
    Main entry point.

    Runs both Discord bot and FastAPI server concurrently using asyncio.
    """
    print("Starting BizBot...")
    print("=" * 50)

    load_dotenv(override=True)

    try:
        await asyncio.gather(start_bot(), run_fastapi())
    except KeyboardInterrupt:
        print("\n\nShutting down BizBot...")
        await stop_bot()
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        await stop_bot()
        raise


if __name__ == "__main__":
    asyncio.run(main())
