from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class Judge(Enum):
    BOJ = "boj"
    CODEFORCES = "codeforces"
    JUNGOL = "jungol"


@dataclass(frozen=True)
class ProblemRef:
    judge: Judge
    problem_id: str
    url: str
    is_gym: bool = False


def parse_problem_url(url: str) -> ProblemRef:
    parsed = urlparse(url)

    host = parsed.netloc.lower()

    if host.startswith("www."):
        host = host[4:]

    path = parsed.path.strip("/")
    parts = path.split("/")

    # BOJ
    if host == "acmicpc.net":
        if (
            len(parts) == 2
            and parts[0] == "problem"
            and parts[1].isdigit()
        ):
            return ProblemRef(
                judge=Judge.BOJ,
                problem_id=parts[1],
                url=url,
            )

    # Codeforces
    if host == "codeforces.com":
        # /problemset/problem/1324/F
        if (
            len(parts) == 4
            and parts[0] == "problemset"
            and parts[1] == "problem"
            and parts[2].isdigit()
        ):
            contest_id = parts[2]
            index = parts[3].upper()

            return ProblemRef(
                judge=Judge.CODEFORCES,
                problem_id=(
                    f"{contest_id}{index}"
                ),
                url=url,
                is_gym=False,
            )

        # /contest/1324/problem/F
        if (
            len(parts) == 4
            and parts[0] == "contest"
            and parts[1].isdigit()
            and parts[2] == "problem"
        ):
            contest_id = parts[1]
            index = parts[3].upper()

            return ProblemRef(
                judge=Judge.CODEFORCES,
                problem_id=(
                    f"{contest_id}{index}"
                ),
                url=url,
                is_gym=False,
            )

        # /gym/102644/problem/C
        if (
            len(parts) == 4
            and parts[0] == "gym"
            and parts[1].isdigit()
            and parts[2] == "problem"
        ):
            contest_id = parts[1]
            index = parts[3].upper()

            return ProblemRef(
                judge=Judge.CODEFORCES,
                problem_id=(
                    f"{contest_id}{index}"
                ),
                url=url,
                is_gym=True,
            )
        
        # /problemset/gymProblem/102644/C
        if (
            len(parts) == 4
            and parts[0] == "problemset"
            and parts[1] == "gymProblem"
            and parts[2].isdigit()
        ):
            contest_id = parts[2]
            index = parts[3].upper()

            return ProblemRef(
                judge=Judge.CODEFORCES,
                problem_id=(
                    f"{contest_id}{index}"
                ),
                url=url,
                is_gym=True,
            )

    raise ValueError(
        f"지원하지 않는 문제 URL입니다: {url}"
    )