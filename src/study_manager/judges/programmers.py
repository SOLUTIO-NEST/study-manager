import html
import re
from dataclasses import dataclass

from curl_cffi import requests

from study_manager.routing.problem_url import (
    ProblemRef,
)


@dataclass
class ProgrammersProblem:
    problem_id: int
    title: str
    level: int | None
    url: str


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


def _extract_title(
    page: str,
) -> str:
    # 현재 프로그래머스 문제 페이지에서
    # 실제 문제 제목에 사용되는 요소
    match = re.search(
        (
            r'<[^>]*class=["\']'
            r'[^"\']*\bchallenge-title\b'
            r'[^"\']*["\'][^>]*>'
            r"(.*?)"
            r"</[^>]+>"
        ),
        page,
        re.IGNORECASE
        | re.DOTALL,
    )

    if match is not None:
        title = _clean_html_text(
            match.group(1)
        )

        if title:
            return title

    # DOM 구조가 바뀌었을 때를 위한 fallback.
    #
    # <title>
    # 코딩테스트 연습 - 방문 길이 | 프로그래머스 스쿨
    # </title>
    match = re.search(
        (
            r"<title[^>]*>\s*"
            r"코딩테스트 연습\s*-\s*"
            r"(.*?)"
            r"\s*\|\s*프로그래머스 스쿨"
            r"\s*</title>"
        ),
        page,
        re.IGNORECASE
        | re.DOTALL,
    )

    if match is not None:
        title = _clean_html_text(
            match.group(1)
        )

        if title:
            return title

    raise ValueError(
        "프로그래머스 문제 제목을 "
        "찾을 수 없습니다."
    )


def _extract_level(
    page: str,
) -> int | None:
    match = re.search(
        (
            r'data-challenge-level='
            r'["\'](\d+)["\']'
        ),
        page,
        re.IGNORECASE,
    )

    if match is None:
        return None

    return int(
        match.group(1)
    )


def _extract_lesson_id(
    page: str,
) -> int | None:
    match = re.search(
        (
            r'data-lesson-id='
            r'["\'](\d+)["\']'
        ),
        page,
        re.IGNORECASE,
    )

    if match is None:
        return None

    return int(
        match.group(1)
    )


def get_problem(
    ref: ProblemRef,
) -> ProgrammersProblem:
    problem_id = int(
        ref.problem_id
    )

    response = requests.get(
        ref.url,
        impersonate="chrome",
        timeout=10,
    )

    response.raise_for_status()

    page = response.text

    page_problem_id = (
        _extract_lesson_id(
            page
        )
    )

    # 페이지에서도 lesson ID를 얻을 수 있으면
    # URL의 ID와 일치하는지 검증한다.
    if (
        page_problem_id is not None
        and page_problem_id != problem_id
    ):
        raise ValueError(
            "URL의 lesson ID와 "
            "페이지의 lesson ID가 다릅니다: "
            f"{problem_id} != {page_problem_id}"
        )

    title = _extract_title(
        page
    )

    level = _extract_level(
        page
    )

    return ProgrammersProblem(
        problem_id=problem_id,
        title=title,
        level=level,

        # 중복 판정은 lesson_id로만 하고,
        # 링크 자체는 사용자가 입력한 링크를 보존
        url=ref.url,
    )