from study_manager.judges import (
    boj,
    codeforces,
    programmers,
)
from study_manager.routing.problem_url import (
    Judge,
    parse_problem_url,
)


def get_problem(
    url: str,
):
    ref = parse_problem_url(
        url
    )

    handlers = {
        Judge.BOJ: boj.get_problem,
        Judge.CODEFORCES: (
            codeforces.get_problem
        ),
        Judge.PROGRAMMERS: (
            programmers.get_problem
        ),
    }

    handler = handlers.get(
        ref.judge
    )

    if handler is None:
        raise ValueError(
            "아직 구현되지 않은 OJ입니다: "
            f"{ref.judge.value}"
        )

    return handler(
        ref
    )