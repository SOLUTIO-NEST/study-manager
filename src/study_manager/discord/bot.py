import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from study_manager.discord.registration_ui import (
    InitialRegistrationModal,
)


load_dotenv()

DISCORD_BOT_TOKEN = os.environ[
    "DISCORD_BOT_TOKEN"
]

DISCORD_GUILD_ID = int(
    os.environ["DISCORD_GUILD_ID"]
)

GUILD = discord.Object(
    id=DISCORD_GUILD_ID
)


class StudyManagerClient(
    discord.Client,
):
    def __init__(self):
        super().__init__(
            intents=discord.Intents.default()
        )

        self.tree = (
            app_commands.CommandTree(
                self
            )
        )

    async def setup_hook(self):
        synced = await self.tree.sync(
            guild=GUILD
        )

        print(
            f"Discord 명령어 "
            f"{len(synced)}개 동기화 완료"
        )

    async def on_ready(self):
        print(
            f"Discord 로그인 완료: "
            f"{self.user}"
        )


client = StudyManagerClient()


@client.tree.command(
    name="문제등록",
    description=(
        "스터디 문제를 Notion에 등록합니다."
    ),
    guild=GUILD,
)
async def problem_register(
    interaction: discord.Interaction,
):
    await interaction.response.send_modal(
        InitialRegistrationModal()
    )


def run_bot():
    client.run(
        DISCORD_BOT_TOKEN
    )