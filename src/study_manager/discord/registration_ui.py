import asyncio
from dataclasses import dataclass, field

import discord

from study_manager.registration import (
    RegistrationResult,
    register,
)
from study_manager.routing.problem_url import (
    Judge,
    parse_problem_url,
)


# ----------------------------------------------------------------------
# Session
# ----------------------------------------------------------------------


@dataclass
class RegistrationSession:
    study_urls: list[str] = field(
        default_factory=list
    )
    problem_urls: list[str] = field(
        default_factory=list
    )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _split_urls(
    *values: str,
) -> list[str]:
    """
    여러 줄짜리 입력을 URL 목록으로 변환한다.

    빈 줄은 무시한다.
    """
    urls = []

    for value in values:
        for line in value.splitlines():
            url = line.strip()

            if url:
                urls.append(url)

    return urls


def _problem_label(
    url: str,
) -> str:
    try:
        ref = parse_problem_url(
            url
        )

        if ref.judge == Judge.BOJ:
            return (
                f"백준 {ref.problem_id}"
            )

        if ref.judge == Judge.CODEFORCES:
            if ref.is_gym:
                return (
                    f"코포 G-{ref.problem_id}"
                )

            return (
                f"코포 {ref.problem_id}"
            )

        if ref.judge == Judge.PROGRAMMERS:
            return (
                f"프머 {ref.problem_id}"
            )

    except Exception:
        pass

    return f"? {url}"


def render_session(
    session: RegistrationSession,
) -> str:
    lines = [
        "**SOLUTIO 문제 등록**",
        "",
        f"스터디 {len(session.study_urls)}개",
    ]

    if session.study_urls:
        for index, url in enumerate(
            session.study_urls,
            start=1,
        ):
            lines.append(
                f"{index}. {url}"
            )
    else:
        lines.append("- 없음")

    lines.extend(
        [
            "",
            f"문제 {len(session.problem_urls)}개",
        ]
    )

    if session.problem_urls:
        for index, url in enumerate(
            session.problem_urls,
            start=1,
        ):
            lines.append(
                f"{index}. {_problem_label(url)}"
            )
    else:
        lines.append("- 없음")

    return "\n".join(lines)


def render_result(
    result: RegistrationResult,
) -> str:
    lines = [
        "**등록 완료**",
        "",
        f"스터디: {len(result.studies)}개",
        f"문제: {len(result.problems)}개",
    ]

    if result.problems:
        lines.extend(
            [
                "",
                "**문제 처리 결과**",
            ]
        )

        for problem in result.problems:
            action = (
                "생성"
                if problem.created
                else "갱신"
            )

            if problem.judge == Judge.BOJ:
                judge_name = "백준"

            elif problem.judge == Judge.CODEFORCES:
                judge_name = "코포"

            elif problem.judge == Judge.PROGRAMMERS:
                judge_name = "프머"

            else:
                judge_name = (
                    problem.judge.value
                )

            lines.append(
                f"✓ [{judge_name} "
                f"{problem.problem_id}] "
                f"{problem.title} "
                f"- {action}"
            )

    if result.issues:
        lines.extend(
            [
                "",
                "**오류 / 경고**",
            ]
        )

        for issue in result.issues:
            lines.append(
                f"✗ {issue.target}: "
                f"{issue.message}"
            )

    return "\n".join(lines)


# ----------------------------------------------------------------------
# Initial modal
# ----------------------------------------------------------------------


class InitialRegistrationModal(
    discord.ui.Modal,
    title="SOLUTIO 문제 등록",
):
    def __init__(self):
        super().__init__()

        self.study_input = (
            discord.ui.TextInput(
                style=(
                    discord.TextStyle.paragraph
                ),
                placeholder=(
                    "스터디 URL을 한 줄에 "
                    "하나씩 입력하세요.\n"
                    "없으면 비워도 됩니다."
                ),
                required=False,
                max_length=4000,
            )
        )

        self.problem_input = (
            discord.ui.TextInput(
                style=(
                    discord.TextStyle.paragraph
                ),
                placeholder=(
                    "문제 URL을 한 줄에 "
                    "하나씩 입력하세요.\n"
                    "백준 / 코포 / Gym / 프머"
                ),
                required=False,
                max_length=4000,
            )
        )

        self.add_item(
            discord.ui.Label(
                text="스터디 URL",
                component=self.study_input,
            )
        )

        self.add_item(
            discord.ui.Label(
                text="문제 URL",
                component=self.problem_input,
            )
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        session = RegistrationSession(
            study_urls=_split_urls(
                self.study_input.value,
            ),
            problem_urls=_split_urls(
                self.problem_input.value,
            ),
        )

        view = RegistrationView(
            session=session,
            owner_id=interaction.user.id,
        )

        await interaction.response.send_message(
            render_session(
                session
            ),
            view=view,
            ephemeral=True,
        )


# ----------------------------------------------------------------------
# Add study modal
# ----------------------------------------------------------------------


class AddStudyModal(
    discord.ui.Modal,
    title="스터디 추가",
):
    def __init__(
        self,
        parent_view: "RegistrationView",
    ):
        super().__init__()

        self.parent_view = (
            parent_view
        )

        self.study_input = (
            discord.ui.TextInput(
                style=(
                    discord.TextStyle.paragraph
                ),
                placeholder=(
                    "추가할 스터디 URL을 "
                    "한 줄에 하나씩 입력하세요."
                ),
                required=False,
                max_length=4000,
            )
        )

        self.add_item(
            discord.ui.Label(
                text="스터디 URL",
                component=self.study_input,
            )
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        urls = _split_urls(
            self.study_input.value
        )

        self.parent_view.session.study_urls.extend(
            urls
        )

        await interaction.response.edit_message(
            content=render_session(
                self.parent_view.session
            ),
            view=self.parent_view,
        )


# ----------------------------------------------------------------------
# Add problems modal
# ----------------------------------------------------------------------


class AddProblemsModal(
    discord.ui.Modal,
    title="문제 추가",
):
    def __init__(
        self,
        parent_view: "RegistrationView",
    ):
        super().__init__()

        self.parent_view = (
            parent_view
        )

        self.problem_input = (
            discord.ui.TextInput(
                style=(
                    discord.TextStyle.paragraph
                ),
                placeholder=(
                    "추가할 문제 URL을 "
                    "한 줄에 하나씩 입력하세요."
                ),
                required=False,
                max_length=4000,
            )
        )

        self.add_item(
            discord.ui.Label(
                text="문제 URL",
                component=self.problem_input,
            )
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        urls = _split_urls(
            self.problem_input.value
        )

        self.parent_view.session.problem_urls.extend(
            urls
        )

        await interaction.response.edit_message(
            content=render_session(
                self.parent_view.session
            ),
            view=self.parent_view,
        )


# ----------------------------------------------------------------------
# Main registration view
# ----------------------------------------------------------------------


class RegistrationView(
    discord.ui.View,
):
    def __init__(
        self,
        session: RegistrationSession,
        owner_id: int,
    ):
        super().__init__(
            timeout=15 * 60
        )

        self.session = session
        self.owner_id = owner_id

        # 실행 버튼 중복 클릭 방지
        self.processing = False

    def _set_buttons_disabled(
        self,
        disabled: bool,
    ) -> None:
        for item in self.children:
            if isinstance(
                item,
                discord.ui.Button,
            ):
                item.disabled = disabled

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        # 본인의 세션인지 확인
        if (
            interaction.user.id
            != self.owner_id
        ):
            await interaction.response.send_message(
                (
                    "이 등록 화면은 "
                    "다른 사용자의 세션입니다."
                ),
                ephemeral=True,
            )

            return False

        # Discord 화면에 disabled가
        # 반영되기 전에 빠르게 다시 눌러도 차단
        if self.processing:
            await interaction.response.send_message(
                "현재 등록 작업이 진행 중입니다.",
                ephemeral=True,
            )

            return False

        return True

    # ------------------------------------------------------------------
    # + Study
    # ------------------------------------------------------------------

    @discord.ui.button(
        label="+ 스터디",
        style=(
            discord.ButtonStyle.secondary
        ),
    )
    async def add_study(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(
            AddStudyModal(
                self
            )
        )

    # ------------------------------------------------------------------
    # + Problem
    # ------------------------------------------------------------------

    @discord.ui.button(
        label="+ 문제",
        style=(
            discord.ButtonStyle.secondary
        ),
    )
    async def add_problem(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(
            AddProblemsModal(
                self
            )
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    @discord.ui.button(
        label="실행",
        style=(
            discord.ButtonStyle.success
        ),
    )
    async def execute(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not self.session.problem_urls:
            await interaction.response.send_message(
                "등록할 문제 URL이 없습니다.",
                ephemeral=True,
            )
            return

        # 중요:
        # 첫 await 이전에 처리 상태로 변경
        # → 빠른 더블 클릭도 막음
        self.processing = True

        # 모든 버튼 비활성화
        self._set_buttons_disabled(
            True
        )

        # 사용자에게 즉시
        # "처리 중" 상태 표시
        await interaction.response.edit_message(
            content=(
                render_session(
                    self.session
                )
                + "\n\n"
                + "⏳ **등록 처리 중...**"
            ),
            view=self,
        )

        try:
            # register() 내부는 동기 HTTP 작업이므로
            # Discord 이벤트 루프를 막지 않게
            # 별도 thread에서 실행
            result = await asyncio.to_thread(
                register,
                self.session.study_urls,
                self.session.problem_urls,
            )

            self.stop()

            # 실제 Notion 반영까지 모두 끝난 뒤
            # 완료 화면으로 변경
            await interaction.edit_original_response(
                content=render_result(
                    result
                ),
                view=None,
            )

        except Exception as error:
            # 실패했다면 다시 수정/재실행할 수 있게
            # 버튼을 복구
            self.processing = False

            self._set_buttons_disabled(
                False
            )

            await interaction.edit_original_response(
                content=(
                    render_session(
                        self.session
                    )
                    + "\n\n"
                    + "**등록 실패**\n"
                    + str(error)
                ),
                view=self,
            )

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    @discord.ui.button(
        label="취소",
        style=(
            discord.ButtonStyle.danger
        ),
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content="등록을 취소했습니다.",
            view=None,
        )