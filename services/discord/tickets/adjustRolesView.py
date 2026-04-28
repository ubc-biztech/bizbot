import discord

from .discordRolesStore import (
    add_configured_roles,
    cleanup_deleted_roles_from_config,
    get_discord_roles_table_name,
    list_configured_role_ids,
    list_configured_roles_in_guild,
    remove_configured_roles,
)


class AdjustRolesRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="Select ticket-ping roles...",
            min_values=1,
            max_values=25,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, AdjustRolesView):
            await interaction.response.send_message(
                "Could not resolve role editor state.",
                ephemeral=True,
            )
            return

        view.selected_role_ids = {role.id for role in self.values}
        await interaction.response.defer(ephemeral=True, thinking=False)


class AdjustRolesView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=300)
        self.guild = guild
        self.selected_role_ids: set[int] = set()
        self.add_item(AdjustRolesRoleSelect())

    async def _send_current_roles(self, interaction: discord.Interaction) -> None:
        configured_roles = await list_configured_roles_in_guild(self.guild)
        if configured_roles:
            role_mentions = "\n".join(role.mention for role in configured_roles)
        else:
            role_mentions = "_No roles configured yet._"

        table_name = get_discord_roles_table_name(self.guild.id)
        await interaction.followup.send(
            (f"Table: `{table_name}`\nCurrent ticket-ping roles:\n{role_mentions}"),
            ephemeral=True,
        )

    @discord.ui.button(label="Add Selected", style=discord.ButtonStyle.success)
    async def add_selected(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        _ = button
        if not self.selected_role_ids:
            await interaction.response.send_message(
                "Select at least one role first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        existing_role_ids = set(await list_configured_role_ids(self.guild.id))
        final_role_count = len(existing_role_ids | self.selected_role_ids)
        if final_role_count > 25:
            await interaction.followup.send(
                (
                    "Discord dropdowns only support 25 options. "
                    "Your selection would result in "
                    f"{final_role_count} configured roles."
                ),
                ephemeral=True,
            )
            return

        added_count = await add_configured_roles(
            guild_id=self.guild.id,
            role_ids=self.selected_role_ids,
        )
        await cleanup_deleted_roles_from_config(self.guild)

        await interaction.followup.send(
            f"Added {added_count} new role(s) to the DB.",
            ephemeral=True,
        )
        await self._send_current_roles(interaction)

    @discord.ui.button(label="Remove Selected", style=discord.ButtonStyle.danger)
    async def remove_selected(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        _ = button
        if not self.selected_role_ids:
            await interaction.response.send_message(
                "Select at least one role first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        removed_count = await remove_configured_roles(
            guild_id=self.guild.id,
            role_ids=self.selected_role_ids,
        )
        await cleanup_deleted_roles_from_config(self.guild)
        await interaction.followup.send(
            f"Removed {removed_count} role(s) from the DB.",
            ephemeral=True,
        )
        await self._send_current_roles(interaction)

    @discord.ui.button(label="Show Configured", style=discord.ButtonStyle.secondary)
    async def show_configured(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        _ = button
        await interaction.response.defer(ephemeral=True, thinking=False)
        await cleanup_deleted_roles_from_config(self.guild)
        await self._send_current_roles(interaction)
