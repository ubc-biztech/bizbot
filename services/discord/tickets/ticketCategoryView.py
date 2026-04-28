import discord

from .ticketCategorySelect import TicketCategorySelect


class TicketCategoryView(discord.ui.View):
    def __init__(self, roles: list[discord.Role]):
        super().__init__(timeout=90)
        self.add_item(TicketCategorySelect(roles))
