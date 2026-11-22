import asyncio

import discord

from study_manager.discord.permissions import (
    has_staff_role,
)
from study_manager.discord.registration_ui import (
    InitialRegistrationModal,
)
from study_manager.refresh import (
    RefreshPlan,
    build_refresh_plan,
    refresh_manager,
)


_refresh_task: asyncio.Task | None = None


def render_status() -> str:
    status = refresh_manager.snapshot()

    if status is None:
        return "아직 실행한 전체 갱신이 없습니다."

    lines = [
        f"**전체 정보 갱신: {status.state}**",
        f"대상: {status.total}개",
        f"갱신: {status.updated}개",
        f"실패: {status.failed}개",
        f"건너뜀: {status.skipped}개",
    ]

    if status.state == "진행 중":
        lines.append(
            f"현재: {status.current}"
        )

    if status.issues:
        lines.extend(
            [
                "",
                "**오류 (최대 10개)**",
                *status.issues,
            ]
        )

    return "\n".join(lines)[:1900]


async def check_staff(
    interaction: discord.Interaction,
) -> bool:
    if has_staff_role(interaction):
        return True

    await interaction.response.send_message(
        "운영진 역할이 있어야 사용할 수 있습니다.",
        ephemeral=True,
    )

    return False


class ManagementView(
    discord.ui.View,
):
    def __init__(
        self,
        owner_id: int,
        staff: bool,
    ):
        super().__init__(
            timeout=15 * 60
        )

        self.owner_id = owner_id

        if not staff:
            self.remove_item(
                self.refresh_database
            )

            self.remove_item(
                self.refresh_status
            )

            self.remove_item(
                self.cancel_refresh
            )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "다른 사용자의 관리 화면입니다.",
                ephemeral=True,
            )

            return False

        return True

    @discord.ui.button(
        label="문제 등록",
        style=discord.ButtonStyle.primary,
    )
    async def register_problem(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(
            InitialRegistrationModal()
        )

    @discord.ui.button(
        label="데베 전체 초기화",
        style=discord.ButtonStyle.secondary,
    )
    async def refresh_database(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not await check_staff(interaction):
            return

        status = refresh_manager.snapshot()

        if status is not None and status.state == "진행 중":
            await interaction.response.send_message(
                render_status(),
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        try:
            plan = await asyncio.to_thread(
                build_refresh_plan
            )

            counts = "\n".join(
                f"{name}: {len(pages)}개"
                for name, pages in plan.pages.items()
            )

            await interaction.edit_original_response(
                content=(
                    "**전체 문제 정보를 갱신할까요?**\n\n"
                    + counts
                    + "\n\n제목·난이도·태그를 최신 정보로 갱신합니다.\n"
                    "풀이·본문·문제 번호·링크·스터디 연결은 유지됩니다.\n"
                    "순차 처리하므로 시간이 걸릴 수 있습니다."
                ),
                view=RefreshConfirmationView(
                    owner_id=self.owner_id,
                    plan=plan,
                ),
            )

        except Exception as error:
            await interaction.edit_original_response(
                content=(
                    "갱신 대상을 확인하지 못했습니다.\n"
                    f"{str(error)[:500]}"
                ),
                view=None,
            )

    @discord.ui.button(
        label="진행 상황",
        style=discord.ButtonStyle.secondary,
    )
    async def refresh_status(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not await check_staff(interaction):
            return

        await interaction.response.edit_message(
            content=render_status(),
            view=self,
        )

    @discord.ui.button(
        label="갱신 중단",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel_refresh(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not await check_staff(interaction):
            return

        cancelled = refresh_manager.cancel()

        await interaction.response.send_message(
            (
                "중단을 요청했습니다. 현재 문제 처리 후 멈춥니다."
                if cancelled
                else "진행 중인 갱신이 없습니다."
            ),
            ephemeral=True,
        )


class RefreshConfirmationView(
    discord.ui.View,
):
    def __init__(
        self,
        owner_id: int,
        plan: RefreshPlan,
    ):
        super().__init__(
            timeout=2 * 60
        )

        self.owner_id = owner_id
        self.plan = plan

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "다른 사용자의 확인 화면입니다.",
                ephemeral=True,
            )

            return False

        return await check_staff(interaction)

    @discord.ui.button(
        label="전체 정보 갱신",
        style=discord.ButtonStyle.success,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        global _refresh_task

        # 버튼을 누르기 전에 역할이 회수된 경우도 차단한다.
        if not await check_staff(interaction):
            return

        try:
            job = refresh_manager.start(
                self.plan
            )
        except ValueError as error:
            await interaction.response.send_message(
                str(error),
                ephemeral=True,
            )
            return

        # 상태를 먼저 예약한 뒤 작업을 시작해 중복 클릭을 막는다.
        # Discord의 15분 응답 수명과 별개로 작업은 계속된다.
        _refresh_task = asyncio.create_task(
            asyncio.to_thread(
                refresh_manager.run,
                job,
            )
        )

        self.stop()

        await interaction.response.edit_message(
            content=(
                "전체 정보 갱신을 시작했습니다.\n"
                "진행 상황 버튼으로 확인할 수 있습니다.\n"
                "화면이 만료되면 /스터디관리를 다시 열어주세요."
            ),
            view=ManagementView(
                owner_id=self.owner_id,
                staff=True,
            ),
        )

    @discord.ui.button(
        label="취소",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not await check_staff(interaction):
            return

        self.stop()

        await interaction.response.edit_message(
            content="전체 갱신을 취소했습니다.",
            view=None,
        )
