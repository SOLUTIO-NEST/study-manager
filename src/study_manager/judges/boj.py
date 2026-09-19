from dataclasses import dataclass

from curl_cffi import requests

from study_manager.routing.problem_url import Judge, ProblemRef


SOLVEDAC_BASE_URL = "https://solved.ac/api/v3"


@dataclass
class BojProblem:
    problem_id: int
    title: str
    tier: str | None
    tags: list[str]
    url: str


def convert_level(level: int) -> str | None:
    if level == 0:
        return None

    tiers = ["B", "S", "G", "P", "D", "R"]

    group = (level - 1) // 5
    rank = 5 - ((level - 1) % 5)

    return f"{tiers[group]}{rank}"


def get_korean_tags(data: dict) -> list[str]:
    tags = []

    for tag in data.get("tags", []):
        for display_name in tag.get("displayNames", []):
            if display_name.get("language") == "ko":
                tags.append(display_name["name"])
                break

    return tags


def get_problem(ref: ProblemRef) -> BojProblem:
    if ref.judge != Judge.BOJ:
        raise ValueError("BOJ 문제가 아닙니다.")

    response = requests.get(
        f"{SOLVEDAC_BASE_URL}/problem/lookup",
        params={"problemIds": ref.problem_id},
        impersonate="chrome",
        timeout=10,
        headers={
            "Accept": "application/json",
            "x-solvedac-language": "ko",
        },
    )

    response.raise_for_status()

    problems = response.json()

    if not problems:
        raise ValueError(
            f"BOJ {ref.problem_id}번 문제 정보를 찾을 수 없습니다."
        )

    data = problems[0]

    return BojProblem(
        problem_id=data["problemId"],
        title=data["titleKo"],
        tier=convert_level(data["level"]),
        tags=get_korean_tags(data),
        url=ref.url,
    )