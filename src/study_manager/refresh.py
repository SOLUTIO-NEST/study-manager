import threading
import time
from dataclasses import dataclass, field

import httpx

from study_manager.judges import get_problem
from study_manager.judges import codeforces as judge_codeforces
from study_manager.network import (
    NOTION_GATE,
    request,
)
from study_manager.notion import (
    codeforces,
    programmers,
    solvedac,
)
from study_manager.notion.api import (
    NOTION_API_URL,
    headers,
)
from study_manager.routing.problem_url import (
    Judge,
    parse_problem_url,
)


DATABASES = {
    "솔브닥": (
        solvedac.SOLVEDAC_DATA_SOURCE_ID,
        solvedac,
        {
            Judge.SOLVEDAC,
            Judge.BOJ,
            Judge.DOJ,
            Judge.JUNGOL,
        },
    ),
    "코포": (
        codeforces.CODEFORCES_DATA_SOURCE_ID,
        codeforces,
        {Judge.CODEFORCES},
    ),
    "프머": (
        programmers.PROGRAMMERS_DATA_SOURCE_ID,
        programmers,
        {Judge.PROGRAMMERS},
    ),
}

REFRESH_COOLDOWN_SECONDS = 10 * 60


@dataclass
class RefreshPlan:
    pages: dict[str, list[dict]]

    @property
    def total(self) -> int:
        return sum(
            len(pages)
            for pages in self.pages.values()
        )


@dataclass
class RefreshStatus:
    total: int
    state: str = "진행 중"
    current: str = "준비 중"
    updated: int = 0
    failed: int = 0
    skipped: int = 0
    issues: list[str] = field(
        default_factory=list
    )


@dataclass
class RefreshJob:
    plan: RefreshPlan
    status: RefreshStatus
    cancel: threading.Event = field(
        default_factory=threading.Event
    )


def build_refresh_plan() -> RefreshPlan:
    pages = {}

    for name, (source_id, _, _) in DATABASES.items():
        pages[name] = []
        start_cursor = None

        while True:
            body = {
                "page_size": 100,
            }

            if start_cursor is not None:
                body["start_cursor"] = start_cursor

            response = request(
                NOTION_GATE,
                httpx.post,
                (
                    f"{NOTION_API_URL}"
                    f"/data_sources/{source_id}/query"
                ),
                headers=headers(),
                json=body,
                timeout=10.0,
            )

            response.raise_for_status()

            data = response.json()

            pages[name].extend(
                data["results"]
            )

            if not data["has_more"]:
                break

            start_cursor = data["next_cursor"]

    return RefreshPlan(
        pages=pages,
    )


class RefreshManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.job: RefreshJob | None = None
        self.next_start = 0.0

    def start(
        self,
        plan: RefreshPlan,
    ) -> RefreshJob:
        with self.lock:
            if self.job is not None:
                if self.job.status.state == "진행 중":
                    raise ValueError(
                        "이미 전체 갱신이 진행 중입니다."
                    )

            remaining = (
                self.next_start
                - time.monotonic()
            )

            if remaining > 0:
                raise ValueError(
                    "반복 실행을 줄이기 위해 "
                    f"{int(remaining) + 1}초 후 다시 실행할 수 있습니다."
                )

            if plan.total == 0:
                raise ValueError(
                    "갱신할 문제가 없습니다."
                )

            self.job = RefreshJob(
                plan=plan,
                status=RefreshStatus(
                    total=plan.total,
                ),
            )

            return self.job

    def snapshot(self) -> RefreshStatus | None:
        with self.lock:
            if self.job is None:
                return None

            status = self.job.status

            return RefreshStatus(
                total=status.total,
                state=status.state,
                current=status.current,
                updated=status.updated,
                failed=status.failed,
                skipped=status.skipped,
                issues=list(status.issues),
            )

    def cancel(self) -> bool:
        with self.lock:
            if (
                self.job is None
                or self.job.status.state != "진행 중"
            ):
                return False

            self.job.cancel.set()

            return True

    def run(
        self,
        job: RefreshJob,
    ) -> None:
        cache = {}

        try:
            judge_codeforces.clear_problemset_cache()

            for name, pages in job.plan.pages.items():
                _, handler, judges = DATABASES[name]

                for index, page in enumerate(pages):
                    if job.cancel.is_set():
                        return

                    with self.lock:
                        job.status.current = (
                            f"{name} {index + 1}/{len(pages)}"
                        )

                    try:
                        url = (
                            page["properties"]
                            ["문제 링크"]["url"]
                        )

                        ref = parse_problem_url(
                            url or ""
                        )

                        if ref.judge not in judges:
                            raise ValueError(
                                "문제 링크와 DB의 OJ가 다릅니다."
                            )

                        key = (
                            ref.judge,
                            ref.problem_id,
                            ref.is_gym,
                        )

                        if key not in cache:
                            cache[key] = get_problem(
                                url
                            )

                        problem = cache[key]

                        # 프로그래머스 페이지 구조가 바뀌면
                        # 기존 레벨을 빈 값으로 덮어쓰지 않는다.
                        if (
                            ref.judge == Judge.PROGRAMMERS
                            and problem.level is None
                        ):
                            raise ValueError(
                                "문제 레벨을 확인할 수 없습니다."
                            )

                        handler.update_problem_metadata(
                            page["id"],
                            problem,
                            preserve_identity=True,
                        )

                        with self.lock:
                            job.status.updated += 1

                    except Exception as error:
                        response = getattr(
                            error,
                            "response",
                            None,
                        )

                        status_code = getattr(
                            response,
                            "status_code",
                            None,
                        )

                        with self.lock:
                            job.status.failed += 1

                            if len(job.status.issues) < 10:
                                job.status.issues.append(
                                    f"{name} {page['id']}: "
                                    f"{str(error)[:160]}"
                                )

                            if status_code in {401, 403, 429, 529}:
                                job.status.skipped += (
                                    len(pages) - index - 1
                                )

                        # 인증 실패나 호출 제한 후에는
                        # 같은 DB에 대한 요청을 계속 보내지 않는다.
                        if status_code in {401, 403, 429, 529}:
                            break

        except Exception as error:
            with self.lock:
                job.status.state = "실패"
                job.status.issues.append(
                    str(error)[:160]
                )

        finally:
            with self.lock:
                if job.status.state != "실패":
                    job.status.state = (
                        "중단"
                        if job.cancel.is_set()
                        else "완료"
                    )

                job.status.skipped = (
                    job.status.total
                    - job.status.updated
                    - job.status.failed
                )

                self.next_start = (
                    time.monotonic()
                    + REFRESH_COOLDOWN_SECONDS
                )


refresh_manager = RefreshManager()
