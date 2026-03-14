"""
Test cog for BizBot.

Provides testing commands including DynamoDB connectivity test.
"""

import discord
from discord import app_commands
from discord.ext import commands
from bots.dynamodb import db_client


class TestCog(commands.Cog):
    """Testing commands for BizBot."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="ping", description="Test bot responsiveness")
    async def ping(self, interaction: discord.Interaction):
        """Simple ping command to test if the bot is responding."""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"🏓 Pong! Latency: {latency}ms",
            ephemeral=True
        )
    
    @app_commands.command(name="test-db", description="Test DynamoDB connectivity")
    async def test_db(self, interaction: discord.Interaction):
        """
        Test DynamoDB connection by scanning the table.
        
        Returns up to 5 items from the configured table.
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            items = await db_client.scan_table(limit=5)
            
            if items:
                item_list = "\n".join([f"• {item}" for item in items[:3]])
                message = (
                    f"✓ **DynamoDB Connection Successful**\n"
                    f"Table: `{db_client.table_name}`\n"
                    f"Items found: {len(items)}\n\n"
                    f"Sample items:\n{item_list}"
                )
            else:
                message = (
                    f"✓ **DynamoDB Connection Successful**\n"
                    f"Table: `{db_client.table_name}`\n"
                    f"No items found (table is empty)"
                )
            
            await interaction.followup.send(message, ephemeral=True)
        
        except Exception as e:
            error_message = (
                f"✗ **DynamoDB Connection Failed**\n"
                f"Table: `{db_client.table_name}`\n"
                f"Error: ```{str(e)}```"
            )
            await interaction.followup.send(error_message, ephemeral=True)
    
    @app_commands.command(name="get-item", description="Get a specific item from DynamoDB")
    @app_commands.describe(ticket_id="The ticket ID to retrieve")
    async def get_item(self, interaction: discord.Interaction, ticket_id: str):
        """
        Get a specific item from DynamoDB by ticket_id.
        
        Modify the key structure based on your table schema.
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Modify this key to match your table's primary key structure
            item = await db_client.get_item({"ticket_id": ticket_id})
            
            if item:
                message = (
                    f"✓ **Item Found**\n"
                    f"```json\n{item}\n```"
                )
            else:
                message = f"✗ **Item Not Found**\nNo item with ticket_id `{ticket_id}` exists."
            
            await interaction.followup.send(message, ephemeral=True)
        
        except Exception as e:
            error_message = (
                f"✗ **Query Failed**\n"
                f"Error: ```{str(e)}```"
            )
            await interaction.followup.send(error_message, ephemeral=True)


async def setup(bot: commands.Bot):
    """Load the TestCog."""
    await bot.add_cog(TestCog(bot))
