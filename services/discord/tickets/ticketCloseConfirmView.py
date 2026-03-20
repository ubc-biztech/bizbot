import discord


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        _ = button
        await interaction.response.send_message(
            "TODO",
            ephemeral=True,
        )
