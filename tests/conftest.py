import os

import httpx
import pytest

from study_manager import network

# 테스트에서는 로컬 .env 대신 가짜 설정만 사용한다.
for name in [
    "NOTION_TOKEN",
    "NOTION_STUDY_DATA_SOURCE_ID",
    "NOTION_SOLVEDAC_DATA_SOURCE_ID",
    "NOTION_CODEFORCES_DATA_SOURCE_ID",
    "NOTION_PROGRAMMERS_DATA_SOURCE_ID",
    "NOTION_ATCODER_DATA_SOURCE_ID",
    "SOLVEDAC_CLIENT_ID",
    "SOLVEDAC_CLIENT_SECRET",
]:
    os.environ[name] = "test"


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    for gate in [
        network.SOLVEDAC_GATE,
        network.CODEFORCES_GATE,
        network.PROGRAMMERS_GATE,
        network.ATCODER_GATE,
        network.NOTION_GATE,
    ]:
        monkeypatch.setattr(gate, "interval", 0.0)
        monkeypatch.setattr(gate, "next_request", 0.0)

    monkeypatch.setattr(
        network.time,
        "sleep",
        lambda seconds: None,
    )

    def blocked(*args, **kwargs):
        raise AssertionError(
            "테스트에서 실제 HTTP 요청을 보내면 안 됩니다."
        )

    for method in [
        "get",
        "post",
        "patch",
        "delete",
    ]:
        monkeypatch.setattr(
            httpx,
            method,
            blocked,
        )


@pytest.fixture
def make_response():
    def response(data, status=200):
        return httpx.Response(
            status,
            json=data,
            request=httpx.Request(
                "GET",
                "https://example.com",
            ),
        )

    return response
