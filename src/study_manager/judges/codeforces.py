import time
from dataclasses import dataclass

import httpx

from study_manager.routing.problem_url import Judge, ProblemRef


API_URL = "https://codeforces.com/api/problemset.problems"
CACHE_TTL = 600

_cached_problems: list[dict] | None = None
_cache_time: float = 0


@dataclass
class CodeforcesProblem:
    contest_id: int
    index: str
    title: str
    rating: int | None
    tags: list[str]
    url: str


def _get_problemset() -> list[dict]:
    global _cached_problems, _cache_time

    now = time.monotonic()

    if (
        _cached_problems is not None
        and now - _cache_time < CACHE_TTL
    ):
        return _cached_problems

    response = httpx.get(
        API_URL,
        timeout=30.0,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("status") != "OK":
        raise RuntimeError(
            f"Codeforces API 오류: {data.get('comment', '알 수 없는 오류')}"
        )

    _cached_problems = data["result"]["problems"]
    _cache_time = now

    return _cached_problems


def get_problem(ref: ProblemRef) -> CodeforcesProblem:
    if ref.judge != Judge.CODEFORCES:
        raise ValueError("Codeforces 문제가 아닙니다.")

    for problem in _get_problemset():
        contest_id = problem.get("contestId")
        index = problem.get("index")

        if contest_id is None or index is None:
            continue

        if f"{contest_id}{index}" != ref.problem_id:
            continue

        return CodeforcesProblem(
            contest_id=contest_id,
            index=index,
            title=problem["name"],
            rating=problem.get("rating"),
            tags=problem.get("tags", []),
            url=ref.url,
        )

    raise ValueError(
        f"Codeforces {ref.problem_id} 문제 정보를 찾을 수 없습니다."
    )