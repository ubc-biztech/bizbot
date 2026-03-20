"""
Verify cog for BizBot.

Provides the /verify slash command that prompts attendees to enter their
BizTech email and checks their registration status in DynamoDB.
"""

from datetime import datetime, timezone # Using this to append the year to the event name
import discord
from discord import app_commands 
from discord.ext import commands

from bots.db import db

REGISTRATIONS_TABLE = "biztechRegistrationsPROD" # Table that is being queried
HACKER_ROLE_NAME = "Hacker" # Role that is being assigned


# Modal that collects the user's BizTech email for verification.
class VerifyModal(discord.ui.Modal):
    email = discord.ui.TextInput(
        label="Enter your Email",
        style=discord.TextStyle.short,
        placeholder="you@example.com",
        required=True,
        max_length=320, 
    )

    # Constructor for the VerifyModal, creates instance variables for the event name and year.
    def __init__(self, event_name: str, year: int) -> None:
        super().__init__(title="Verify Your Registration")
        self.event_name = event_name
        self.year = year

    # Function that is executed when the modal is submitted.
    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True) 

        email_value = self.email.value.strip().lower() # Removes whitespace and converts email to lowercase
        event_key = f"{self.event_name};{self.year}" # Creates the composite key for the DynamoDB query

        # Query biztechRegistrationsPROD with composite key
        try:
            item = await db.get_one_custom(
                {
                    "TableName": REGISTRATIONS_TABLE,
                    "Key": {
                        "id": {"S": email_value},
                        "eventID;year": {"S": event_key},
                    },
                }
            )
        
        except Exception as e:
            await interaction.followup.send(
                "Something went wrong while checking your registration. "
                "Please try again or contact an exec.",
                ephemeral=True,
            )
            return

        if not item:
            await interaction.followup.send(
                f"No registration found for **{email_value}** "
                f"at **{self.event_name}**.\n"
                "Make sure you've registered on the BizTech app and "
                "entered the correct email.",
                ephemeral=True,
            )
            return

        reg_status = item.get("registrationStatus", {}).get("S", "")
        
        if reg_status != "registered":
            await interaction.followup.send(
                f"Your registration status is **{reg_status or 'unknown'}**, "
                f"not **registered**.\n"
                "Please complete your registration on the BizTech app first.",
                ephemeral=True,
            )
            return

        existing_discord_id = item.get("discordId", {}).get("S")
        if existing_discord_id and existing_discord_id != str(interaction.user.id):
            await interaction.followup.send(
                f"This email is already linked to the Discord account <@{existing_discord_id}>.\n"
                "If this is not your account, please contact an exec.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.followup.send(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        hacker_role = discord.utils.get(guild.roles, name=HACKER_ROLE_NAME)
        if not hacker_role:
            await interaction.followup.send(
                f"The **{HACKER_ROLE_NAME}** role doesn't exist in this server. "
                "Please ask an exec to create it.",
                ephemeral=True,
            )
            return

        member = interaction.user
        if hacker_role in member.roles:
            await interaction.followup.send(
                f"You already have the **{HACKER_ROLE_NAME}** role!",
                ephemeral=True,
            )
            return

        try:
            await member.add_roles(hacker_role, reason=f"Verified via /verify ({email_value})")
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to assign roles. "
                "Please ask an exec to check my role position.",
                ephemeral=True,
            )
            return
        
        try:
            await db.update_db_custom(
                {
                    "TableName": REGISTRATIONS_TABLE,
                    "Key": {
                        "id": {"S": email_value},
                        "eventID;year": {"S": event_key},
                    },
                    "UpdateExpression": "SET discordId = :did",
                    "ExpressionAttributeValues": {":did": {"S": str(interaction.user.id)}},
                }
            )
        except Exception as e:
            print(f"Failed to save discordId to DynamoDB: {e}")
        
        await interaction.followup.send(
            f"✅ You've been verified! The **{HACKER_ROLE_NAME}** role has been assigned.",
            ephemeral=True,
        ) 


class VerifyCog(commands.Cog):
    """Verification commands for BizBot."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="verify", description="Verify your event registration")
    async def verify(self, interaction: discord.Interaction) -> None:

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
                "Please use `/verify` inside an event category channel.",
                ephemeral=True,
            )
            return

        event_name = category.name
        year = datetime.now(timezone.utc).year
        await interaction.response.send_modal(VerifyModal(event_name=event_name, year=year))

async def setup(bot: commands.Bot) -> None:
    """Load the VerifyCog."""
    await bot.add_cog(VerifyCog(bot))