from dataclasses import dataclass

from study_manager.judges import get_problem
from study_manager.notion import boj as notion_boj
from study_manager.notion import codeforces as notion_codeforces
from study_manager.notion import programmers as notion_programmers
from study_manager.notion.study import get_study_page
from study_manager.routing.problem_url import (
    Judge,
    ProblemRef,
    parse_problem_url,
)


@dataclass
class RegisteredStudy:
    url: str
    page_id: str
    title: str


@dataclass
class RegisteredProblem:
    url: str
    judge: Judge
    problem_id: str
    title: str
    page_id: str
    created: bool


@dataclass
class RegistrationIssue:
    target: str
    message: str


@dataclass
class RegistrationResult:
    studies: list[RegisteredStudy]
    problems: list[RegisteredProblem]
    issues: list[RegistrationIssue]


def _clean_urls(
    urls: list[str],
) -> list[str]:
    return [
        url.strip()
        for url in urls
        if url.strip()
    ]


def _get_page_title(
    page: dict,
) -> str:
    for prop in page["properties"].values():
        if prop.get("type") != "title":
            continue

        title = "".join(
            item.get("plain_text", "")
            for item in prop.get("title", [])
        )

        if title:
            return title

    return page["id"]


def _display_problem_id(
    ref: ProblemRef,
) -> str:
    if (
        ref.judge == Judge.CODEFORCES
        and ref.is_gym
    ):
        return f"G-{ref.problem_id}"

    return ref.problem_id


def _get_notion_handler(
    judge: Judge,
):
    handlers = {
        Judge.BOJ: notion_boj,
        Judge.CODEFORCES: notion_codeforces,
        Judge.PROGRAMMERS: notion_programmers,
    }

    handler = handlers.get(judge)

    if handler is None:
        raise ValueError(
            f"아직 Notion 연동이 구현되지 않은 OJ입니다: {judge.value}"
        )

    return handler


def _rebuild_study_views(
    study_page_id: str,
) -> None:
    # 먼저 새로 필요한 View들을 생성한다.
    notion_codeforces.rebuild_study_view(
        study_page_id
    )

    notion_programmers.rebuild_study_view(
        study_page_id
    )

    # 기본 BOJ View를 갱신하거나
    # BOJ 문제가 없으면 제거한다.
    notion_boj.rebuild_study_view(
        study_page_id
    )

    # 마지막 View 문제로 첫 패스에서
    # 제거되지 못한 0개짜리 View를 다시 정리한다.
    notion_codeforces.rebuild_study_view(
        study_page_id
    )

    notion_programmers.rebuild_study_view(
        study_page_id
    )


def register(
    study_urls: list[str],
    problem_urls: list[str],
) -> RegistrationResult:
    study_urls = _clean_urls(
        study_urls
    )

    problem_urls = _clean_urls(
        problem_urls
    )

    if not problem_urls:
        raise ValueError(
            "등록할 문제가 없습니다."
        )

    registered_studies = []
    registered_problems = []
    issues = []

    # --------------------------------------------------
    # Study URL 확인
    # --------------------------------------------------

    seen_study_ids = set()

    for url in study_urls:
        try:
            page = get_study_page(
                url
            )

            page_id = page["id"]

            if page_id in seen_study_ids:
                continue

            seen_study_ids.add(
                page_id
            )

            registered_studies.append(
                RegisteredStudy(
                    url=url,
                    page_id=page_id,
                    title=_get_page_title(
                        page
                    ),
                )
            )

        except Exception as e:
            issues.append(
                RegistrationIssue(
                    target=url,
                    message=str(e),
                )
            )

    # --------------------------------------------------
    # Problem 생성 / 갱신
    # --------------------------------------------------

    seen_problem_ids = set()

    for url in problem_urls:
        try:
            ref = parse_problem_url(
                url
            )

            key = (
                ref.judge,
                ref.problem_id,
                ref.is_gym,
            )

            # 같은 문제를 다른 URL 형식으로
            # 여러 번 넣어도 한 번만 처리
            if key in seen_problem_ids:
                continue

            seen_problem_ids.add(
                key
            )

            problem = get_problem(
                url
            )

            handler = _get_notion_handler(
                ref.judge
            )

            page, created = (
                handler.save_problem(
                    problem
                )
            )

            registered_problems.append(
                RegisteredProblem(
                    url=url,
                    judge=ref.judge,
                    problem_id=(
                        _display_problem_id(
                            ref
                        )
                    ),
                    title=problem.title,
                    page_id=page["id"],
                    created=created,
                )
            )

        except Exception as e:
            issues.append(
                RegistrationIssue(
                    target=url,
                    message=str(e),
                )
            )

    # --------------------------------------------------
    # 문제 ↔ 스터디 Relation
    # --------------------------------------------------

    for problem in registered_problems:
        handler = _get_notion_handler(
            problem.judge
        )

        for study in registered_studies:
            try:
                handler.add_study_relation(
                    problem.page_id,
                    study.page_id,
                )

            except Exception as e:
                issues.append(
                    RegistrationIssue(
                        target=(
                            f"{problem.problem_id}"
                            f" -> "
                            f"{study.title}"
                        ),
                        message=str(e),
                    )
                )

    # --------------------------------------------------
    # Study View 재동기화
    # --------------------------------------------------

    for study in registered_studies:
        try:
            _rebuild_study_views(
                study.page_id
            )

        except Exception as e:
            issues.append(
                RegistrationIssue(
                    target=study.title,
                    message=(
                        "스터디 View 갱신 실패: "
                        f"{e}"
                    ),
                )
            )

    return RegistrationResult(
        studies=registered_studies,
        problems=registered_problems,
        issues=issues,
    )