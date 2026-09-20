import html
import re
import time
from dataclasses import dataclass

import httpx
from curl_cffi import requests

from study_manager.routing.problem_url import (
    ProblemRef,
)


CODEFORCES_API_URL = (
    "https://codeforces.com/api"
)

PROBLEMSET_CACHE_SECONDS = 600

_problemset_cache: list[dict] | None = None
_problemset_cache_time = 0.0


@dataclass
class CodeforcesProblem:
    contest_id: int
    index: str
    title: str
    rating: int | None
    tags: list[str]
    url: str
    is_gym: bool = False


def _get_problemset() -> list[dict]:
    global _problemset_cache
    global _problemset_cache_time

    now = time.monotonic()

    if (
        _problemset_cache is not None
        and now - _problemset_cache_time
        < PROBLEMSET_CACHE_SECONDS
    ):
        return _problemset_cache

    response = httpx.get(
        (
            f"{CODEFORCES_API_URL}"
            "/problemset.problems"
        ),
        params={
            "lang": "en",
        },
        timeout=20.0,
    )

    response.raise_for_status()

    data = response.json()

    if data["status"] != "OK":
        raise RuntimeError(
            "Codeforces API 요청에 실패했습니다."
        )

    _problemset_cache = (
        data["result"]["problems"]
    )

    _problemset_cache_time = now

    return _problemset_cache


def _clean_html_text(
    value: str,
) -> str:
    value = re.sub(
        r"<[^>]+>",
        "",
        value,
    )

    return html.unescape(
        value
    ).strip()


def _get_problem_from_page(
    contest_id: int,
    index: str,
    *,
    is_gym: bool,
) -> CodeforcesProblem:
    if is_gym:
        url = (
            "https://codeforces.com/"
            f"gym/{contest_id}/"
            f"problem/{index}"
        )
    else:
        url = (
            "https://codeforces.com/"
            "problemset/problem/"
            f"{contest_id}/{index}"
        )

    response = requests.get(
        url,
        params={
            "locale": "en",
        },
        impersonate="chrome",
        timeout=10,
    )

    response.raise_for_status()

    page = response.text

    # 예:
    # <div class="title">C. Vacations</div>
    title_match = re.search(
        (
            r'<div\s+class=["\']title["\']'
            r"[^>]*>(.*?)</div>"
        ),
        page,
        re.IGNORECASE
        | re.DOTALL,
    )

    if title_match is None:
        raise ValueError(
            "Codeforces 문제 제목을 "
            f"찾을 수 없습니다: {url}"
        )

    title = _clean_html_text(
        title_match.group(1)
    )

    # "C. Vacations"
    # -> "Vacations"
    title = re.sub(
        (
            r"^\s*"
            + re.escape(index)
            + r"\.\s*"
        ),
        "",
        title,
    )

    tags = []
    rating = None

    tag_matches = re.findall(
        (
            r'<span\b[^>]*'
            r'class=["\'][^"\']*'
            r'\btag-box\b'
            r'[^"\']*["\'][^>]*>'
            r"(.*?)"
            r"</span>"
        ),
        page,
        re.IGNORECASE
        | re.DOTALL,
    )

    for raw_tag in tag_matches:
        tag = _clean_html_text(
            raw_tag
        )

        if not tag:
            continue

        if (
            tag.startswith("*")
            and tag[1:].isdigit()
        ):
            rating = int(
                tag[1:]
            )

            continue

        tags.append(
            tag
        )

    return CodeforcesProblem(
        contest_id=contest_id,
        index=index,
        title=title,
        rating=rating,
        tags=tags,
        url=url,
        is_gym=is_gym,
    )


def _get_regular_problem(
    ref: ProblemRef,
) -> CodeforcesProblem:
    match = re.fullmatch(
        r"(\d+)([A-Za-z]\d*)",
        ref.problem_id,
    )

    if match is None:
        raise ValueError(
            "잘못된 Codeforces 문제 ID입니다: "
            f"{ref.problem_id}"
        )

    contest_id_text, index = (
        match.groups()
    )

    contest_id = int(
        contest_id_text
    )

    index = index.upper()

    problems = _get_problemset()

    for item in problems:
        if (
            item.get("contestId")
            == contest_id
            and item.get("index")
            == index
        ):
            return CodeforcesProblem(
                contest_id=contest_id,
                index=index,
                title=item["name"],
                rating=item.get(
                    "rating"
                ),
                tags=item.get(
                    "tags",
                    [],
                ),
                url=(
                    "https://codeforces.com/"
                    "problemset/problem/"
                    f"{contest_id}/{index}"
                ),
                is_gym=False,
            )

    # 699C 같은 Div.1 / Div.2 공유 문제 등은
    # problemset.problems에서 해당 ID가
    # 빠질 수 있으므로 실제 문제 페이지에서
    # 메타데이터를 가져온다.
    return _get_problem_from_page(
        contest_id,
        index,
        is_gym=False,
    )


def _get_gym_problem(
    ref: ProblemRef,
) -> CodeforcesProblem:
    match = re.fullmatch(
        r"(\d+)([A-Za-z]\d*)",
        ref.problem_id,
    )

    if match is None:
        raise ValueError(
            "잘못된 Gym 문제 ID입니다: "
            f"{ref.problem_id}"
        )

    contest_id_text, index = (
        match.groups()
    )

    contest_id = int(
        contest_id_text
    )

    index = index.upper()

    return _get_problem_from_page(
        contest_id,
        index,
        is_gym=True,
    )


def get_problem(
    ref: ProblemRef,
) -> CodeforcesProblem:
    if ref.is_gym:
        return _get_gym_problem(
            ref
        )

    return _get_regular_problem(
        ref
    )