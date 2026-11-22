from dataclasses import replace
from unittest.mock import Mock

import httpx
import pytest

from study_manager import registration
from study_manager.judges.solvedac import (
    SolvedacProblem,
)
from study_manager.notion import solvedac
from study_manager.routing.problem_url import Judge


@pytest.fixture
def problem():
    return SolvedacProblem(
        problem_id=19759,
        sub_id="",
        title="문제 제목",
        level=4,
        tier="B2",
        tags=["구현"],
        gives_no_rating=False,
        judge_ids=[
            {
                "ojId": "boj",
                "problemId": "19759",
                "subId": "",
            },
            {
                "ojId": "boj",
                "problemId": "28955",
                "subId": "",
            },
        ],
        url="https://solved.ac/p/19759",
    )


def make_page(page_id, url):
    return {
        "id": page_id,
        "properties": {
            "문제 링크": {
                "url": url,
            },
        },
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://www.acmicpc.net/problem/28955",
        "https://solved.ac/p/19759",
        "https://solved.ac/en/p/19759",
    ],
)
def test_existing_page_is_reused(
    monkeypatch,
    make_response,
    problem,
    url,
):
    page = make_page("existing", url)

    def post(target, **kwargs):
        assert target.endswith("/query")

        return make_response(
            {
                "results": [page],
                "has_more": False,
            },
        )

    def patch(target, **kwargs):
        assert target.endswith("/pages/existing")
        assert set(kwargs["json"]) == {"icon", "properties"}
        assert set(kwargs["json"]["properties"]) == {
            "이름",
            "문제 번호",
            "티어",
            "태그",
            "문제 링크",
        }

        return make_response(page)

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "patch", patch)
    monkeypatch.setattr(
        solvedac,
        "_get_problem_icon",
        lambda problem: {"type": "custom_emoji"},
    )

    saved, created = solvedac.save_problem(problem)

    assert saved["id"] == "existing"
    assert created is False


def test_subproblems_do_not_overwrite_each_other(
    monkeypatch,
    make_response,
    problem,
):
    problem = replace(
        problem,
        problem_id=19917,
        sub_id="b",
        judge_ids=[],
        url="https://solved.ac/p/19917b",
    )

    pages = [
        make_page("a", "https://solved.ac/p/19917a"),
        make_page("b", "https://solved.ac/p/19917b"),
    ]

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: make_response(
            {
                "results": pages,
                "has_more": False,
            },
        ),
    )

    assert solvedac.find_problem(problem)["id"] == "b"


def test_duplicate_legacy_pages_are_not_merged(
    monkeypatch,
    make_response,
    problem,
):
    pages = [
        make_page("first", "https://acmicpc.net/problem/19759"),
        make_page("second", "https://acmicpc.net/problem/28955"),
    ]

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: make_response(
            {
                "results": pages,
                "has_more": False,
            },
        ),
    )

    with pytest.raises(
        ValueError,
        match="여러 개",
    ):
        solvedac.save_problem(problem)


def test_existing_page_search_uses_pagination(
    monkeypatch,
    make_response,
    problem,
):
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs["json"])

        if len(calls) == 1:
            return make_response(
                {
                    "results": [],
                    "has_more": True,
                    "next_cursor": "next",
                },
            )

        assert kwargs["json"]["start_cursor"] == "next"

        return make_response(
            {
                "results": [
                    make_page("found", problem.url),
                ],
                "has_more": False,
            },
        )

    monkeypatch.setattr(httpx, "post", post)

    assert solvedac.find_problem(problem)["id"] == "found"


def test_unrated_icon_uses_rating_flag(problem):
    unrated = replace(
        problem,
        level=0,
        gives_no_rating=False,
    )

    not_ratable = replace(
        unrated,
        gives_no_rating=True,
    )

    assert solvedac.get_marker_name(unrated) == "00"
    assert solvedac.get_marker_name(not_ratable) == "nr"


def test_study_view_name_is_solvedac(
    monkeypatch,
):
    monkeypatch.setattr(
        solvedac,
        "query_pages_by_relation",
        lambda **kwargs: [{"id": "problem"}],
    )

    monkeypatch.setattr(
        solvedac,
        "get_problem_database_id",
        lambda page_id: "database",
    )

    monkeypatch.setattr(
        solvedac,
        "find_view_id",
        lambda **kwargs: "view",
    )

    monkeypatch.setattr(
        solvedac,
        "_get_view_configuration",
        lambda: {},
    )

    update = Mock()

    monkeypatch.setattr(
        solvedac,
        "update_view",
        update,
    )

    solvedac.rebuild_study_view("study")

    assert update.call_args.kwargs["name"] == "솔브닥 1"


def test_registration_deduplicates_across_judges(
    monkeypatch,
    problem,
):
    monkeypatch.setattr(
        registration,
        "get_problem",
        lambda url: problem,
    )

    monkeypatch.setattr(
        registration,
        "get_study_page",
        lambda url: {
            "id": url,
            "properties": {},
        },
    )

    save = Mock(
        return_value=({"id": "existing"}, False),
    )

    relation = Mock()
    rebuild = Mock()

    monkeypatch.setattr(
        registration.notion_solvedac,
        "save_problem",
        save,
    )

    monkeypatch.setattr(
        registration.notion_solvedac,
        "add_study_relation",
        relation,
    )

    monkeypatch.setattr(
        registration,
        "_rebuild_study_views",
        rebuild,
    )

    result = registration.register(
        ["study-one", "study-two"],
        [
            "https://acmicpc.net/problem/28955",
            "https://solved.ac/p/19759",
            "https://doj.kr/ko/problems/1050",
        ],
    )

    assert len(result.problems) == 1
    assert result.problems[0].judge == Judge.SOLVEDAC
    assert result.problems[0].problem_id == "19759"
    assert result.issues == []
    assert save.call_count == 1
    assert relation.call_count == 2
    assert rebuild.call_count == 2
