import copy

import httpx
import pytest

from study_manager.judges import solvedac
from study_manager.routing.problem_url import (
    Judge,
    parse_problem_url,
)


@pytest.fixture(autouse=True)
def clear_metadata_cache(monkeypatch):
    monkeypatch.setattr(
        solvedac,
        "_judges_cache",
        None,
    )

    monkeypatch.setattr(
        solvedac,
        "_tags_cache",
        None,
    )


@pytest.fixture
def problem_data():
    return {
        "problemId": 19759,
        "subId": "",
        "level": 4,
        "givesNoRating": False,
        "titles": [
            {
                "language": "en",
                "title": "Original title",
                "isOriginal": True,
            },
            {
                "language": "ko",
                "title": "한국어 제목",
                "isOriginal": False,
            },
        ],
        "tags": [
            {
                "key": "impl",
            },
        ],
        "judgeIds": [
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
    }


def test_v4_auth_and_metadata(
    monkeypatch,
    make_response,
    problem_data,
):
    calls = []

    def get(url, **kwargs):
        calls.append(url)

        assert kwargs["headers"]["x-client-id"] == "test"
        assert kwargs["headers"]["x-client-secret"] == "test"
        assert "/api/v4/" in url

        if url.endswith("/tags"):
            return make_response(
                {
                    "tags": [
                        {
                            "key": "impl",
                            "names": {
                                "ko": "구현",
                            },
                        },
                    ],
                },
            )

        assert kwargs["params"] == {"sub": ""}

        return make_response(
            problem_data
        )

    monkeypatch.setattr(
        httpx,
        "get",
        get,
    )

    ref = parse_problem_url(
        "https://solved.ac/p/19759"
    )

    problem = solvedac.get_problem(ref)

    assert problem.title == "한국어 제목"
    assert problem.tier == "B2"
    assert problem.tags == ["구현"]
    assert problem.url == "https://solved.ac/p/19759"

    solvedac.get_problem(ref)

    assert sum(url.endswith("/tags") for url in calls) == 1


@pytest.mark.parametrize(
    "judge, url, native_id, prefix",
    [
        ("boj", "https://acmicpc.net/problem/28955", "28955", "B"),
        ("doj", "https://doj.kr/ko/problems/1050", "1050", "D"),
        ("jungol", "https://jungol.co.kr/problem/3522", "3522", "J"),
    ],
)
def test_native_id_is_resolved_before_detail(
    monkeypatch,
    make_response,
    problem_data,
    judge,
    url,
    native_id,
    prefix,
):
    problem_data["tags"] = []
    problem_data["judgeIds"] = [
        {
            "ojId": judge,
            "problemId": native_id,
            "subId": "",
        },
    ]

    calls = []

    def get(target, **kwargs):
        calls.append(target)

        if target.endswith("/judges"):
            return make_response(
                {
                    "judges": [
                        {
                            "id": judge,
                            "prefix": prefix,
                            "aliases": [judge],
                        },
                    ],
                },
            )

        if target.endswith("/problems"):
            assert kwargs["params"]["q"] == f"id:{prefix}{native_id}"

            return make_response(
                {
                    "problems": [problem_data],
                    "total": 1,
                    "pageSize": 50,
                },
            )

        assert target.endswith("/problems/19759")

        return make_response(
            problem_data
        )

    monkeypatch.setattr(httpx, "get", get)

    problem = solvedac.get_problem(
        parse_problem_url(url)
    )

    assert problem.problem_id == 19759
    assert len(calls) == 3


def test_subproblem_keeps_suffix(
    monkeypatch,
    make_response,
    problem_data,
):
    problem_data.update(
        problemId=19917,
        subId="a",
        tags=[],
    )

    def get(url, **kwargs):
        assert url.endswith("/problems/19917")
        assert kwargs["params"] == {"sub": "a"}

        return make_response(
            problem_data
        )

    monkeypatch.setattr(httpx, "get", get)

    problem = solvedac.get_problem(
        parse_problem_url(
            "https://solved.ac/en/p/19917a"
        )
    )

    assert problem.display_id == "19917a"
    assert problem.url == "https://solved.ac/p/19917a"


@pytest.mark.parametrize("multiple", [False, True])
def test_search_never_guesses_problem_identity(
    monkeypatch,
    make_response,
    problem_data,
    multiple,
):
    problems = []

    if multiple:
        other = copy.deepcopy(problem_data)
        other["subId"] = "b"
        problems = [problem_data, other]

    def get(url, **kwargs):
        if url.endswith("/judges"):
            return make_response(
                {
                    "judges": [
                        {
                            "id": "boj",
                            "prefix": "B",
                            "aliases": [],
                        },
                    ],
                },
            )

        assert url.endswith("/problems")

        return make_response(
            {
                "problems": problems,
                "total": len(problems),
                "pageSize": 50,
            },
        )

    monkeypatch.setattr(httpx, "get", get)

    with pytest.raises(ValueError):
        solvedac.get_problem(
            parse_problem_url(
                "https://acmicpc.net/problem/19759"
            )
        )


def test_missing_credentials_are_reported(monkeypatch):
    monkeypatch.delenv(
        "SOLVEDAC_CLIENT_SECRET"
    )

    with pytest.raises(
        ValueError,
        match="SOLVEDAC_CLIENT_SECRET",
    ):
        solvedac.get_problem(
            parse_problem_url(
                "https://solved.ac/p/1000"
            )
        )


@pytest.mark.parametrize("status", [401, 404, 429])
def test_api_errors_do_not_fall_back_to_v3(
    monkeypatch,
    make_response,
    status,
):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: make_response({}, status),
    )

    with pytest.raises(httpx.HTTPStatusError):
        solvedac.get_problem(
            parse_problem_url(
                "https://solved.ac/p/1000"
            )
        )


@pytest.mark.parametrize(
    "url, judge, problem_id",
    [
        ("https://solved.ac/p/1000", Judge.SOLVEDAC, "1000"),
        ("https://solved.ac/ko/p/19917a?from=list", Judge.SOLVEDAC, "19917a"),
        ("https://solved.ac/en/p/19917b/", Judge.SOLVEDAC, "19917b"),
        ("https://www.acmicpc.net/problem/01000", Judge.BOJ, "1000"),
        ("https://doj.kr/ko/problems/1050", Judge.DOJ, "1050"),
        ("https://www.doj.kr/en/problems/1050", Judge.DOJ, "1050"),
        ("https://jungol.co.kr/problem/3522?lang=en", Judge.JUNGOL, "3522"),
        ("https://www.jungol.co.kr/bbs/board.php?bo_table=pbank&wr_id=1001", Judge.JUNGOL, "1001"),
        ("https://codeforces.com/contest/1324/problem/F", Judge.CODEFORCES, "1324F"),
        ("https://codeforces.com/gym/102644/problem/C", Judge.CODEFORCES, "102644C"),
        ("https://school.programmers.co.kr/learn/courses/30/lessons/118668", Judge.PROGRAMMERS, "118668"),
    ],
)
def test_problem_urls(url, judge, problem_id):
    ref = parse_problem_url(url)

    assert ref.judge == judge
    assert ref.problem_id == problem_id


@pytest.mark.parametrize(
    "url",
    [
        "https://solved.ac/ko",
        "https://solved.ac/p/0",
        "https://solved.ac/p/abc",
        "https://solved.ac.example.com/p/1000",
        "https://doj.kr/ko/problems/cipherguess",
    ],
)
def test_unsupported_urls(url):
    with pytest.raises(ValueError):
        parse_problem_url(url)
