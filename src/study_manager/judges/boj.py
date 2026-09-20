from dataclasses import dataclass

from curl_cffi import requests

from study_manager.routing.problem_url import Judge, ProblemRef


SOLVEDAC_BASE_URL = "https://solved.ac/api/v3"


@dataclass
class BojProblem:
    problem_id: int
    title: str

    level: int
    tier: str | None

    tags: list[str]

    sprout: bool
    is_solvable: bool
    gives_no_rating: bool

    url: str


def convert_level(level: int) -> str | None:
    if level == 0:
        return None

    if level == 31:
        return "M"

    if not 1 <= level <= 30:
        raise ValueError(f"알 수 없는 BOJ 난이도입니다: {level}")

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
        params={
            "problemIds": ref.problem_id,
        },
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
    level = data["level"]

    return BojProblem(
        problem_id=data["problemId"],
        title=data["titleKo"],
        level=level,
        tier=convert_level(level),
        tags=get_korean_tags(data),
        sprout=data.get("sprout", False),
        is_solvable=data.get("isSolvable", True),
        gives_no_rating=data.get("givesNoRating", False),
        url=ref.url,
    )