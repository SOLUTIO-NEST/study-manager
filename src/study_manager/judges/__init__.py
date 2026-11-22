from study_manager.judges import (
    codeforces,
    programmers,
    solvedac,
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
        Judge.SOLVEDAC: solvedac.get_problem,
        Judge.BOJ: solvedac.get_problem,
        Judge.DOJ: solvedac.get_problem,
        Judge.JUNGOL: solvedac.get_problem,
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
