import discord

from .ticketCreateModal import TicketCreateModal


class TicketCategorySelect(discord.ui.Select):
    def __init__(self, roles: list[discord.Role]):
        options = [
            discord.SelectOption(label=role.name, value=str(role.id)) for role in roles
        ]

        super().__init__(
            placeholder="Select what you need help with...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_role_id = self.values[0]
        await interaction.response.send_modal(TicketCreateModal(selected_role_id))

        try:
            await interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException) as e:
            print(e)
            pass
