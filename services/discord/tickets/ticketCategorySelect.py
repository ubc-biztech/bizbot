import discord

from services.discord.constants.temp_discord_roles import MENTOR_ROLE_TO_ID_DICTIONARY

from .ticketCreateModal import TicketCreateModal


class TicketCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=category, value=category)
            for category in MENTOR_ROLE_TO_ID_DICTIONARY.keys()
        ]

        super().__init__(
            placeholder="Select what you need help with...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_help_category = self.values[0]
        await interaction.response.send_modal(TicketCreateModal(selected_help_category))

        try:
            await interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException) as e:
            print(e)
            pass
