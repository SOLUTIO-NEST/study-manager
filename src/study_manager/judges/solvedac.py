import os
import re
import time
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

from study_manager.network import (
    SOLVEDAC_GATE,
    request,
)
from study_manager.routing.problem_url import (
    Judge,
    ProblemRef,
)


load_dotenv()

SOLVEDAC_BASE_URL = "https://solved.ac/api/v4"

METADATA_CACHE_SECONDS = 600

_judges_cache: list[dict] | None = None
_judges_cache_time = 0.0
_tags_cache: dict[str, str] | None = None
_tags_cache_time = 0.0


@dataclass
class SolvedacProblem:
    problem_id: int
    sub_id: str
    title: str

    level: int
    tier: str | None

    tags: list[str]
    gives_no_rating: bool
    judge_ids: list[dict]

    url: str

    @property
    def display_id(self) -> str:
        return f"{self.problem_id}{self.sub_id}"


def _get(
    path: str,
    params: dict | None = None,
) -> dict:
    client_id = os.getenv(
        "SOLVEDAC_CLIENT_ID"
    )

    client_secret = os.getenv(
        "SOLVEDAC_CLIENT_SECRET"
    )

    if not client_id or not client_secret:
        raise ValueError(
            "solved.ac API 설정이 없습니다. "
            "SOLVEDAC_CLIENT_ID와 "
            "SOLVEDAC_CLIENT_SECRET을 설정하세요."
        )

    response = request(
        SOLVEDAC_GATE,
        httpx.get,
        f"{SOLVEDAC_BASE_URL}{path}",
        cost=3 if path == "/problems" else 1,
        params=params,
        headers={
            "Accept": "application/json",
            "Accept-Language": "ko",
            "x-client-id": client_id,
            "x-client-secret": client_secret,
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


def convert_level(
    level: int,
) -> str | None:
    if level == 0:
        return None

    if level == 31:
        return "M"

    if not 1 <= level <= 30:
        raise ValueError(
            "알 수 없는 solved.ac "
            f"난이도입니다: {level}"
        )

    tiers = ["B", "S", "G", "P", "D", "R"]

    group = (level - 1) // 5
    rank = 5 - ((level - 1) % 5)

    return f"{tiers[group]}{rank}"


def _get_judges() -> list[dict]:
    global _judges_cache
    global _judges_cache_time

    now = time.monotonic()

    if (
        _judges_cache is not None
        and now - _judges_cache_time
        < METADATA_CACHE_SECONDS
    ):
        return _judges_cache

    _judges_cache = _get(
        "/judges"
    )["judges"]

    _judges_cache_time = now

    return _judges_cache


def _get_tag_names() -> dict[str, str]:
    global _tags_cache
    global _tags_cache_time

    now = time.monotonic()

    if (
        _tags_cache is not None
        and now - _tags_cache_time
        < METADATA_CACHE_SECONDS
    ):
        return _tags_cache

    tags = _get(
        "/tags"
    )["tags"]

    _tags_cache = {
        tag["key"]: (
            tag["names"].get("ko")
            or tag["names"].get("en")
            or tag["key"]
        )
        for tag in tags
    }

    _tags_cache_time = now

    return _tags_cache


def _resolve_judge_problem(
    ref: ProblemRef,
) -> tuple[int, str]:
    judge = next(
        (
            judge
            for judge in _get_judges()
            if (
                judge["id"] == ref.judge.value
                or ref.judge.value
                in judge["aliases"]
            )
        ),
        None,
    )

    if judge is None:
        raise ValueError(
            "solved.ac에 연계되지 않은 "
            f"OJ입니다: {ref.judge.value}"
        )

    matches = {}
    page = 1

    while True:
        data = _get(
            "/problems",
            params={
                "q": (
                    f"id:{judge['prefix']}"
                    f"{ref.problem_id}"
                ),
                "page": page,
            },
        )

        for problem in data["problems"]:
            # 검색 결과의 원래 OJ 번호를 확인한다.
            # solved.ac 번호가 OJ 번호와 같다고 가정하지 않는다.
            if any(
                item["ojId"] == judge["id"]
                and item["problemId"] == ref.problem_id
                for item in problem["judgeIds"]
            ):
                key = (
                    problem["problemId"],
                    problem["subId"],
                )

                matches[key] = problem

        if page * data["pageSize"] >= data["total"]:
            break

        page += 1

    if not matches:
        raise ValueError(
            "solved.ac에서 문제 정보를 "
            "찾을 수 없습니다: "
            f"{ref.judge.value} {ref.problem_id}"
        )

    if len(matches) > 1:
        raise ValueError(
            "여러 세부 문제로 연결된 문제입니다. "
            "등록할 세부 문제의 solved.ac URL을 입력하세요."
        )

    return next(iter(matches))


def _get_title(
    titles: list[dict],
) -> str:
    for title in titles:
        if title["language"] == "ko":
            return title["title"]

    for title in titles:
        if title["isOriginal"]:
            return title["title"]

    if titles:
        return titles[0]["title"]

    raise ValueError(
        "solved.ac 문제 제목이 없습니다."
    )


def get_problem(
    ref: ProblemRef,
) -> SolvedacProblem:
    if ref.judge == Judge.SOLVEDAC:
        match = re.fullmatch(
            r"([1-9][0-9]*)([a-zA-Z0-9_-]*)",
            ref.problem_id,
        )

        if match is None:
            raise ValueError(
                "잘못된 solved.ac 문제 ID입니다: "
                f"{ref.problem_id}"
            )

        problem_id = int(
            match.group(1)
        )

        sub_id = match.group(2)

    elif ref.judge in {
        Judge.BOJ,
        Judge.DOJ,
        Judge.JUNGOL,
    }:
        problem_id, sub_id = (
            _resolve_judge_problem(
                ref
            )
        )

    else:
        raise ValueError(
            "solved.ac 연동 대상이 "
            f"아닙니다: {ref.judge.value}"
        )

    data = _get(
        f"/problems/{problem_id}",
        params={
            "sub": sub_id,
        },
    )

    tag_names = (
        _get_tag_names()
        if data["tags"]
        else {}
    )

    level = data["level"]

    return SolvedacProblem(
        problem_id=data["problemId"],
        sub_id=data["subId"],
        title=_get_title(
            data["titles"]
        ),
        level=level,
        tier=convert_level(level),
        tags=[
            tag_names.get(
                tag["key"],
                tag["key"],
            )
            for tag in data["tags"]
        ],
        gives_no_rating=data["givesNoRating"],
        judge_ids=data["judgeIds"],
        url=(
            "https://solved.ac/p/"
            f"{data['problemId']}{data['subId']}"
        ),
    )
