import math
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from study_manager.network import (
    ATCODER_GATE,
    request,
)
from study_manager.routing.problem_url import (
    ProblemRef,
)


ATCODER_PROBLEMS_URL = "https://kenkoooo.com/atcoder/resources"
METADATA_CACHE_SECONDS = 60 * 60

_metadata_lock = threading.Lock()
_metadata_cache: tuple[dict[str, str], set[tuple[str, str]], dict] | None = None
_metadata_cache_time = 0.0


@dataclass
class AtCoderProblem:
    problem_id: str
    title: str
    difficulty: int | None
    url: str


def _get_resource(
    name: str,
):
    response = request(
        ATCODER_GATE,
        httpx.get,
        f"{ATCODER_PROBLEMS_URL}/{name}.json",
        timeout=20.0,
    )

    response.raise_for_status()
    return response.json()


def clear_metadata_cache() -> None:
    global _metadata_cache

    with _metadata_lock:
        _metadata_cache = None


def _get_metadata() -> tuple[dict[str, str], set[tuple[str, str]], dict]:
    global _metadata_cache
    global _metadata_cache_time

    with _metadata_lock:
        if (
            _metadata_cache is not None
            and time.monotonic() - _metadata_cache_time
            < METADATA_CACHE_SECONDS
        ):
            return _metadata_cache

        titles = {
            problem["id"]: problem["name"]
            for problem in _get_resource("problems")
        }

        # 같은 문제가 원래 대회와 연습 대회 등에 함께 올라갈 수 있다.
        contest_problems = {
            (pair["contest_id"], pair["problem_id"])
            for pair in _get_resource("contest-problem")
        }

        models = _get_resource("problem-models")
        _metadata_cache = titles, contest_problems, models
        _metadata_cache_time = time.monotonic()

        return _metadata_cache


def get_problem(
    ref: ProblemRef,
) -> AtCoderProblem:
    contest_id = urlparse(ref.url).path.split("/")[2]
    problem_id = ref.problem_id
    titles, contest_problems, models = _get_metadata()

    title = titles.get(problem_id)

    if not title or (contest_id, problem_id) not in contest_problems:
        raise ValueError(
            "AtCoder Problems에서 문제를 찾을 수 없습니다: "
            f"{contest_id}/{problem_id}"
        )

    difficulty = models.get(problem_id, {}).get("difficulty")

    # AtCoder Problems 화면과 동일한 표시 난이도를 사용한다.
    if difficulty is not None and difficulty < 400:
        difficulty = math.floor(
            400 * math.exp(difficulty / 400 - 1) + 0.5
        )

    return AtCoderProblem(
        problem_id=problem_id,
        title=title,
        difficulty=difficulty,
        url=ref.url,
    )
