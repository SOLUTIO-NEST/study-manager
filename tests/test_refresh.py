from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from study_manager import refresh
from study_manager.judges.solvedac import SolvedacProblem
from study_manager.routing.problem_url import Judge


def page(page_id, url):
    return {
        "id": page_id,
        "properties": {
            "문제 링크": {"url": url},
        },
    }


@pytest.fixture
def database(monkeypatch):
    handler = SimpleNamespace(
        update_problem_metadata=Mock(),
    )

    monkeypatch.setattr(
        refresh,
        "DATABASES",
        {
            "솔브닥": (
                "source",
                handler,
                {Judge.SOLVEDAC},
            ),
        },
    )

    return handler


def test_all_pages_are_listed(
    monkeypatch,
    make_response,
    database,
):
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs["json"])

        return make_response(
            {
                "results": [{"id": str(len(calls))}],
                "has_more": len(calls) == 1,
                "next_cursor": "next",
            },
        )

    monkeypatch.setattr(httpx, "post", post)

    plan = refresh.build_refresh_plan()

    assert plan.total == 2
    assert calls[1]["start_cursor"] == "next"


def test_refresh_updates_existing_pages_only(
    monkeypatch,
    database,
):
    problem = object()
    fetch = Mock(return_value=problem)

    monkeypatch.setattr(refresh, "get_problem", fetch)

    plan = refresh.RefreshPlan(
        pages={
            "솔브닥": [
                page("one", "https://solved.ac/p/1000"),
                page("two", "https://solved.ac/p/1000"),
            ],
        },
    )

    manager = refresh.RefreshManager()
    manager.run(manager.start(plan))

    assert fetch.call_count == 1
    assert database.update_problem_metadata.call_count == 2
    assert database.update_problem_metadata.call_args.kwargs == {
        "preserve_identity": True,
    }
    assert manager.snapshot().updated == 2
    assert manager.snapshot().state == "완료"


def test_overlap_and_immediate_restart_are_blocked(
    monkeypatch,
    database,
):
    monkeypatch.setattr(
        refresh,
        "get_problem",
        lambda url: object(),
    )

    manager = refresh.RefreshManager()
    plan = refresh.RefreshPlan(
        {"솔브닥": [page("one", "https://solved.ac/p/1000")]},
    )
    job = manager.start(plan)

    with pytest.raises(ValueError, match="진행 중"):
        manager.start(plan)

    manager.run(job)

    with pytest.raises(ValueError, match="초 후"):
        manager.start(plan)


def test_cancel_leaves_remaining_pages_untouched(database):
    manager = refresh.RefreshManager()
    job = manager.start(
        refresh.RefreshPlan(
            {"솔브닥": [page("one", "https://solved.ac/p/1000")]},
        ),
    )

    assert manager.cancel() is True
    manager.run(job)

    assert manager.snapshot().state == "중단"
    assert manager.snapshot().skipped == 1
    database.update_problem_metadata.assert_not_called()


def test_blocked_provider_is_not_repeated(
    monkeypatch,
    database,
    make_response,
):
    response = make_response({}, 429)
    fetch = Mock(
        side_effect=httpx.HTTPStatusError(
            "limited",
            request=response.request,
            response=response,
        ),
    )

    monkeypatch.setattr(refresh, "get_problem", fetch)

    manager = refresh.RefreshManager()
    manager.run(
        manager.start(
            refresh.RefreshPlan(
                {
                    "솔브닥": [
                        page("one", "https://solved.ac/p/1000"),
                        page("two", "https://solved.ac/p/1001"),
                    ],
                },
            ),
        ),
    )

    assert fetch.call_count == 1
    assert manager.snapshot().failed == 1
    assert manager.snapshot().skipped == 1


def test_one_bad_url_does_not_stop_other_pages(
    monkeypatch,
    database,
):
    monkeypatch.setattr(
        refresh,
        "get_problem",
        lambda url: object(),
    )

    manager = refresh.RefreshManager()
    manager.run(
        manager.start(
            refresh.RefreshPlan(
                {
                    "솔브닥": [
                        page("bad", "https://example.com"),
                        page("ok", "https://solved.ac/p/1000"),
                    ],
                },
            ),
        ),
    )

    assert manager.snapshot().failed == 1
    assert manager.snapshot().updated == 1


def test_metadata_refresh_preserves_identity_and_user_data(
    monkeypatch,
    make_response,
):
    problem = SolvedacProblem(
        problem_id=19759,
        sub_id="",
        title="새 제목",
        level=4,
        tier="B2",
        tags=["구현"],
        gives_no_rating=False,
        judge_ids=[],
        url="https://solved.ac/p/19759",
    )

    monkeypatch.setattr(
        refresh.solvedac,
        "_get_problem_icon",
        lambda problem: {},
    )

    payloads = []

    def patch(url, **kwargs):
        payloads.append(kwargs["json"])
        return make_response({})

    monkeypatch.setattr(httpx, "patch", patch)

    refresh.solvedac.update_problem_metadata(
        "existing",
        problem,
        preserve_identity=True,
    )

    assert set(payloads[0]) == {"icon", "properties"}
    assert set(payloads[0]["properties"]) == {
        "이름", "티어", "태그",
    }


def test_all_databases_use_their_own_handlers(monkeypatch):
    monkeypatch.setattr(
        refresh,
        "get_problem",
        lambda url: SimpleNamespace(level=1),
    )

    handlers = [
        refresh.solvedac,
        refresh.codeforces,
        refresh.programmers,
        refresh.atcoder,
    ]
    updates = []

    for handler in handlers:
        update = Mock()
        updates.append(update)
        monkeypatch.setattr(
            handler,
            "update_problem_metadata",
            update,
        )

    manager = refresh.RefreshManager()
    manager.run(
        manager.start(
            refresh.RefreshPlan(
                {
                    "솔브닥": [page("one", "https://solved.ac/p/1000")],
                    "코포": [page("two", "https://codeforces.com/contest/1324/problem/F")],
                    "프머": [page("three", "https://school.programmers.co.kr/learn/courses/30/lessons/118668")],
                    "AtCoder": [page("four", "https://atcoder.jp/contests/abc300/tasks/abc300_a")],
                },
            ),
        ),
    )

    assert manager.snapshot().updated == 4
    for update in updates:
        update.assert_called_once()
        assert update.call_args.kwargs["preserve_identity"] is True


def test_missing_programmers_level_is_not_written(monkeypatch):
    monkeypatch.setattr(
        refresh,
        "get_problem",
        lambda url: SimpleNamespace(level=None),
    )

    update = Mock()
    monkeypatch.setattr(
        refresh.programmers,
        "update_problem_metadata",
        update,
    )

    manager = refresh.RefreshManager()
    manager.run(
        manager.start(
            refresh.RefreshPlan(
                {
                    "프머": [
                        page(
                            "three",
                            "https://school.programmers.co.kr/learn/courses/30/lessons/118668",
                        ),
                    ],
                },
            ),
        ),
    )

    update.assert_not_called()
    assert manager.snapshot().failed == 1
