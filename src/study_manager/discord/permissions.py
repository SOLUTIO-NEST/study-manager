import os

import discord


def has_staff_role(
    interaction: discord.Interaction,
) -> bool:
    if (
        interaction.guild_id is None
        or not isinstance(
            interaction.user,
            discord.Member,
        )
    ):
        return False

    role_id = os.getenv(
        "DISCORD_STAFF_ROLE_ID"
    )

    if role_id:
        if not role_id.isdigit():
            return False

        return any(
            role.id == int(role_id)
            for role in interaction.user.roles
        )

    return any(
        role.name == "운영진"
        for role in interaction.user.roles
    )
