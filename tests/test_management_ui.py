import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from study_manager.discord import management_ui
from study_manager.discord.permissions import has_staff_role
from study_manager.refresh import (
    RefreshManager,
    RefreshPlan,
)


def interaction(roles, user_id=1, guild_id=123):
    member = Mock(spec=discord.Member)
    member.id = user_id
    member.roles = [
        SimpleNamespace(id=role_id, name=name)
        for role_id, name in roles
    ]

    return SimpleNamespace(
        user=member,
        guild_id=guild_id,
        response=SimpleNamespace(
            send_message=AsyncMock(),
            edit_message=AsyncMock(),
        ),
    )


@pytest.fixture(autouse=True)
def use_role_name(monkeypatch):
    monkeypatch.delenv(
        "DISCORD_STAFF_ROLE_ID",
        raising=False,
    )


def test_only_staff_role_is_accepted():
    assert has_staff_role(interaction([(10, "운영진")]))
    assert not has_staff_role(interaction([(20, "회원")]))
    assert not has_staff_role(interaction([]))
    assert not has_staff_role(
        interaction([(10, "운영진")], guild_id=None),
    )


def test_configured_role_id_has_priority(monkeypatch):
    monkeypatch.setenv("DISCORD_STAFF_ROLE_ID", "10")

    assert has_staff_role(interaction([(10, "이름 변경")]))
    assert not has_staff_role(interaction([(20, "운영진")]))

    monkeypatch.setenv("DISCORD_STAFF_ROLE_ID", "invalid")

    assert not has_staff_role(interaction([(10, "운영진")]))


def test_nonstaff_cannot_see_refresh_buttons():
    async def check():
        regular = management_ui.ManagementView(1, staff=False)
        staff = management_ui.ManagementView(1, staff=True)

        assert [item.label for item in regular.children] == ["문제 등록"]
        assert "데베 전체 초기화" in [item.label for item in staff.children]

    asyncio.run(check())


def test_revoked_role_cannot_confirm(monkeypatch):
    manager = RefreshManager()
    monkeypatch.setattr(management_ui, "refresh_manager", manager)

    async def check():
        view = management_ui.RefreshConfirmationView(
            owner_id=1,
            plan=RefreshPlan({}),
        )
        revoked = interaction([])

        await view.confirm.callback(revoked)

        assert manager.snapshot() is None
        revoked.response.send_message.assert_awaited_once()

    asyncio.run(check())


def test_other_user_cannot_control_a_session():
    async def check():
        view = management_ui.ManagementView(1, staff=True)
        other = interaction([(10, "운영진")], user_id=2)

        assert not await view.interaction_check(other)
        other.response.send_message.assert_awaited_once()

    asyncio.run(check())


def test_forged_nonstaff_button_is_rejected():
    async def check():
        view = management_ui.ManagementView(1, staff=True)
        regular = interaction([])

        await view.refresh_database.callback(regular)

        regular.response.send_message.assert_awaited_once()

    asyncio.run(check())


def test_confirmation_cannot_start_two_workers(monkeypatch):
    manager = RefreshManager()
    monkeypatch.setattr(management_ui, "refresh_manager", manager)
    workers = []

    def create_task(coroutine):
        workers.append(coroutine)
        coroutine.close()
        return Mock()

    monkeypatch.setattr(
        management_ui.asyncio,
        "create_task",
        create_task,
    )

    async def check():
        plan = RefreshPlan({"솔브닥": [{"id": "one"}]})
        view = management_ui.RefreshConfirmationView(1, plan)
        staff = interaction([(10, "운영진")])

        await view.confirm.callback(staff)
        await view.confirm.callback(staff)

        assert len(workers) == 1
        staff.response.send_message.assert_awaited_once()

    asyncio.run(check())
