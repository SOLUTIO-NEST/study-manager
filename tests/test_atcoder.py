from unittest.mock import Mock

import httpx

from study_manager import registration
from study_manager.judges import atcoder
from study_manager.notion import atcoder as notion_atcoder


def test_atcoder_registration_reuses_problem_across_contests(
    monkeypatch,
    make_response,
):
    resource = Mock(
        side_effect=[
            [{"id": "abc300_a", "name": "N-choice question"}],
            [
                {"contest_id": "abc300", "problem_id": "abc300_a"},
                {"contest_id": "adt_all_20231220_2", "problem_id": "abc300_a"},
            ],
            {"abc300_a": {"difficulty": -1147}},
        ],
    )

    monkeypatch.setattr(atcoder, "_metadata_cache", None)
    monkeypatch.setattr(atcoder, "_metadata_cache_time", 0.0)
    monkeypatch.setattr(atcoder, "_get_resource", resource)

    page = {"id": "atcoder-page"}
    post = Mock(
        side_effect=[
            make_response({"results": []}),
            make_response(page),
            make_response({"results": [page]}),
        ],
    )
    patch = Mock(return_value=make_response(page))

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "patch", patch)

    original = "https://atcoder.jp/contests/abc300/tasks/abc300_a"
    alias = "https://atcoder.jp/contests/adt_all_20231220_2/tasks/abc300_a"
    invalid = "https://atcoder.jp/contests/abc301/tasks/abc300_a"

    first = registration.register([], [invalid, original + "?lang=en", alias])
    second = registration.register([], [alias])

    assert len(first.issues) == 1
    assert first.issues[0].target == invalid
    assert len(first.problems) == len(second.problems) == 1
    assert first.problems[0].created
    assert not second.problems[0].created
    assert first.problems[0].page_id == second.problems[0].page_id == page["id"]

    first_query, create, second_query = post.call_args_list
    assert first_query.kwargs["json"]["filter"] == {
        "property": "문제 번호",
        "rich_text": {"equals": "abc300_a"},
    }
    assert first_query == second_query
    assert create.kwargs["json"]["template"] == {"type": "default"}
    assert create.kwargs["json"]["properties"]["문제 링크"] == {"url": original}

    assert patch.call_args.kwargs["json"] == {
        "properties": {
            "이름": {"title": [{"text": {"content": "N-choice question"}}]},
            "난이도": {"number": 8},
        },
    }
    assert resource.call_count == 3


def test_atcoder_missing_difficulty_does_not_clear_existing_value(
    monkeypatch,
    make_response,
):
    patch = Mock(return_value=make_response({"id": "existing"}))
    monkeypatch.setattr(httpx, "patch", patch)

    notion_atcoder.update_problem_metadata(
        "existing",
        atcoder.AtCoderProblem(
            problem_id="practice_1",
            title="Welcome to AtCoder",
            difficulty=None,
            url="https://atcoder.jp/contests/practice/tasks/practice_1",
        ),
        preserve_identity=True,
    )

    assert set(patch.call_args.kwargs["json"]["properties"]) == {"이름"}
