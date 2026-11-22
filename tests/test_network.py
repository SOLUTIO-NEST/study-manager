import httpx
import pytest

from study_manager import network


@pytest.fixture
def fake_clock(monkeypatch):
    clock = {"now": 0.0}

    def sleep(seconds):
        clock["now"] += seconds

    monkeypatch.setattr(
        network.random,
        "uniform",
        lambda lower, upper: 0.0,
    )

    monkeypatch.setattr(
        network.time,
        "monotonic",
        lambda: clock["now"],
    )

    monkeypatch.setattr(
        network.time,
        "sleep",
        sleep,
    )

    return clock


def test_search_cost_is_included_in_spacing(fake_clock):
    gate = network.RequestGate(0.6)
    starts = []

    def get(url):
        starts.append(fake_clock["now"])
        return httpx.Response(200)

    network.request(gate, get, "url", cost=3)
    network.request(gate, get, "url")
    network.request(gate, get, "url")

    assert starts == pytest.approx([0.0, 1.8, 2.4])


def test_retry_after_is_observed(fake_clock):
    gate = network.RequestGate(0.6)
    starts = []

    def get(url):
        starts.append(fake_clock["now"])

        return httpx.Response(
            429 if len(starts) == 1 else 200,
            headers={"Retry-After": "7"},
        )

    response = network.request(gate, get, "url")

    assert response.status_code == 200
    assert starts == [0.0, 7.0]


@pytest.mark.parametrize("status", [429, 529])
def test_repeated_limit_has_bounded_retries(fake_clock, status):
    gate = network.RequestGate(0.6)
    calls = []

    def get(url):
        calls.append(fake_clock["now"])

        return httpx.Response(
            status,
            headers={"Retry-After": "2"},
        )

    assert network.request(gate, get, "url").status_code == status
    assert calls == [0.0, 2.0, 4.0]


def test_long_limit_is_not_retried_early(fake_clock):
    gate = network.RequestGate(0.6)
    calls = []

    def get(url):
        calls.append(fake_clock["now"])

        return httpx.Response(
            429,
            headers={"Retry-After": "120"},
        )

    assert network.request(gate, get, "url").status_code == 429
    assert calls == [0.0]
    assert gate.next_request == 120.0


def test_forbidden_is_not_retried(fake_clock):
    gate = network.RequestGate(1.0)
    calls = []

    def get(url):
        calls.append(url)
        return httpx.Response(403)

    assert network.request(gate, get, "url").status_code == 403
    assert calls == ["url"]


def test_notion_access_restriction_is_not_retried(fake_clock):
    gate = network.RequestGate(0.4)
    calls = []

    def get(url):
        calls.append(url)

        return httpx.Response(
            429,
            json={
                "additional_data": {
                    "rate_limit_reason": "public_api_request_blocked",
                },
            },
        )

    assert network.request(gate, get, "url").status_code == 429
    assert calls == ["url"]
