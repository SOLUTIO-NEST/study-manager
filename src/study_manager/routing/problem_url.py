from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class Judge(Enum):
    BOJ = "boj"
    CODEFORCES = "codeforces"


@dataclass
class ProblemRef:
    judge: Judge
    problem_id: str
    url: str


def parse_problem_url(url: str) -> ProblemRef:
    parsed = urlparse(url)

    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    parts = path.split("/")

    # BOJ
    if host in {"acmicpc.net", "www.acmicpc.net"}:
        if len(parts) == 2 and parts[0] == "problem":
            return ProblemRef(
                judge=Judge.BOJ,
                problem_id=parts[1],
                url=url,
            )

    # Codeforces
    if host in {"codeforces.com", "www.codeforces.com"}:
        # https://codeforces.com/problemset/problem/4/A
        if (
            len(parts) == 4
            and parts[0] == "problemset"
            and parts[1] == "problem"
        ):
            contest_id = parts[2]
            index = parts[3]

            return ProblemRef(
                judge=Judge.CODEFORCES,
                problem_id=f"{contest_id}{index}",
                url=url,
            )

        # https://codeforces.com/contest/4/problem/A
        if (
            len(parts) == 4
            and parts[0] == "contest"
            and parts[2] == "problem"
        ):
            contest_id = parts[1]
            index = parts[3]

            return ProblemRef(
                judge=Judge.CODEFORCES,
                problem_id=f"{contest_id}{index}",
                url=url,
            )

    raise ValueError(f"지원하지 않는 문제 URL입니다: {url}")