import discord

from services.discord.constants.temp_discord_roles import (
    get_mentor_role_to_id_dictionary,
)

from .ticketCreateModal import TicketCreateModal


class TicketCategorySelect(discord.ui.Select):
    def __init__(self, guild_id: int | None):
        mentor_role_to_id_dictionary = get_mentor_role_to_id_dictionary(guild_id)
        options = [
            discord.SelectOption(label=category, value=category)
            for category in mentor_role_to_id_dictionary.keys()
        ]

        super().__init__(
            placeholder="Select what you need help with...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_help_category = self.values[0]
        await interaction.response.send_modal(TicketCreateModal(selected_help_category))

        try:
            await interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException) as e:
            print(e)
            pass
