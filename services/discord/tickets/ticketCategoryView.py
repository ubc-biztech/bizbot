import discord

from .ticketCategorySelect import TicketCategorySelect


class TicketCategoryView(discord.ui.View):
    def __init__(self, guild_id: int | None):
        super().__init__(timeout=90)
        self.add_item(TicketCategorySelect(guild_id))
