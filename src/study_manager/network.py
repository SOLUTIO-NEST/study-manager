import math
import random
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


class RequestGate:
    def __init__(
        self,
        interval: float,
    ):
        self.interval = interval
        self.next_request = 0.0
        self.lock = threading.Lock()

    def call(
        self,
        method,
        url: str,
        cost: int = 1,
        **kwargs,
    ):
        with self.lock:
            delay = (
                self.next_request
                - time.monotonic()
            )

            if delay > 0:
                time.sleep(delay)

            self.next_request = (
                time.monotonic()
                + self.interval * cost
            )

            response = method(
                url,
                **kwargs,
            )

            if response.status_code in {429, 529}:
                self.next_request = max(
                    self.next_request,
                    time.monotonic()
                    + _retry_after(response),
                )

            return response

    def postpone(
        self,
        delay: float,
    ) -> None:
        with self.lock:
            self.next_request = max(
                self.next_request,
                time.monotonic() + delay,
            )


def _retry_after(
    response,
) -> float:
    value = response.headers.get(
        "Retry-After",
        "5",
    )

    try:
        delay = float(value)
    except ValueError:
        try:
            deadline = parsedate_to_datetime(
                value
            )

            delay = (
                deadline
                - datetime.now(timezone.utc)
            ).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return 5.0

    if not math.isfinite(delay):
        return 5.0

    return max(0.0, delay)


def request(
    gate: RequestGate,
    method,
    url: str,
    cost: int = 1,
    **kwargs,
):
    for attempt in range(3):
        response = gate.call(
            method,
            url,
            cost=cost,
            **kwargs,
        )

        if response.status_code not in {429, 529}:
            return response

        try:
            reason = response.json().get(
                "additional_data",
                {},
            ).get("rate_limit_reason")
        except (ValueError, AttributeError):
            reason = None

        if reason == "public_api_request_blocked":
            return response

        # 긴 대기는 호출자에게 오류로 돌려준다.
        # gate에는 Retry-After가 남아 다음 요청도 일찍 나가지 않는다.
        if (
            attempt == 2
            or _retry_after(response) > 60
        ):
            return response

        gate.postpone(
            max(
                _retry_after(response),
                2 ** attempt,
            )
            + random.uniform(0.0, 0.25)
        )


# solved.ac 검색은 3 units, 일반 요청은 1 unit을 사용한다.
SOLVEDAC_GATE = RequestGate(0.6)
CODEFORCES_GATE = RequestGate(2.1)
PROGRAMMERS_GATE = RequestGate(1.0)
ATCODER_GATE = RequestGate(1.1)
NOTION_GATE = RequestGate(0.4)
