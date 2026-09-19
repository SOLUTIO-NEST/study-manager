from study_manager.judges import boj, codeforces
from study_manager.routing.problem_url import Judge, parse_problem_url


def get_problem(url: str):
    ref = parse_problem_url(url)

    handlers = {
        Judge.BOJ: boj.get_problem,
        Judge.CODEFORCES: codeforces.get_problem,
    }

    handler = handlers.get(ref.judge)

    if handler is None:
        raise ValueError(f"아직 지원하지 않는 OJ입니다: {ref.judge}")

    return handler(ref)