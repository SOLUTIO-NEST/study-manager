import os
import re
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from study_manager.notion.api import (
    NOTION_API_URL,
    headers,
)


load_dotenv()

STUDY_DATA_SOURCE_ID = os.environ[
    "NOTION_STUDY_DATA_SOURCE_ID"
]


def parse_study_page_id(
    url: str,
) -> str:
    parsed = urlparse(url)

    if parsed.netloc.lower() not in {
        "notion.so",
        "www.notion.so",
        "app.notion.com",
    }:
        raise ValueError(
            f"Notion URL이 아닙니다: {url}"
        )

    last_part = (
        parsed.path
        .rstrip("/")
        .split("/")[-1]
    )

    compact = last_part.replace(
        "-",
        "",
    )

    match = re.search(
        r"([0-9a-fA-F]{32})$",
        compact,
    )

    if match is None:
        raise ValueError(
            "Notion page ID를 "
            f"찾을 수 없습니다: {url}"
        )

    raw = match.group(1)

    return (
        f"{raw[0:8]}-"
        f"{raw[8:12]}-"
        f"{raw[12:16]}-"
        f"{raw[16:20]}-"
        f"{raw[20:32]}"
    )


def validate_study_page(
    page_id: str,
) -> dict:
    response = httpx.get(
        f"{NOTION_API_URL}/pages/{page_id}",
        headers=headers(),
        timeout=10.0,
    )

    response.raise_for_status()

    page = response.json()
    parent = page["parent"]

    if (
        parent.get("type")
        != "data_source_id"
        or parent.get(
            "data_source_id"
        )
        != STUDY_DATA_SOURCE_ID
    ):
        raise ValueError(
            "해당 페이지는 스터디 "
            "데이터베이스의 항목이 아닙니다."
        )

    return page


def get_study_page(
    url: str,
) -> dict:
    page_id = parse_study_page_id(
        url
    )

    return validate_study_page(
        page_id
    )


def _get_page_blocks(
    page_id: str,
) -> list[dict]:
    blocks = []
    start_cursor = None

    while True:
        params = {
            "page_size": 100,
        }

        if start_cursor is not None:
            params["start_cursor"] = (
                start_cursor
            )

        response = httpx.get(
            (
                f"{NOTION_API_URL}"
                f"/blocks/{page_id}/children"
            ),
            headers=headers(),
            params=params,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

        blocks.extend(
            data["results"]
        )

        if not data["has_more"]:
            break

        start_cursor = (
            data["next_cursor"]
        )

    return blocks


def _get_block_text(
    block: dict,
) -> str:
    block_type = block["type"]

    content = block.get(
        block_type,
        {},
    )

    rich_text = content.get(
        "rich_text",
        [],
    )

    return "".join(
        text.get(
            "plain_text",
            "",
        )
        for text in rich_text
    )


def get_problem_database_id(
    study_page_id: str,
) -> str:
    blocks = _get_page_blocks(
        study_page_id
    )

    for index, block in enumerate(
        blocks
    ):
        if block["type"] not in {
            "heading_1",
            "heading_2",
            "heading_3",
        }:
            continue

        if (
            _get_block_text(block)
            != "스터디 문제 리스트"
        ):
            continue

        if index + 1 >= len(blocks):
            break

        next_block = (
            blocks[index + 1]
        )

        if (
            next_block["type"]
            != "child_database"
        ):
            raise ValueError(
                "'스터디 문제 리스트' "
                "바로 아래에 문제 "
                "데이터베이스가 없습니다."
            )

        return next_block["id"]

    raise ValueError(
        "'스터디 문제 리스트' "
        "섹션을 찾을 수 없습니다."
    )

def get_all_study_pages() -> list[dict]:
    pages = []
    start_cursor = None

    while True:
        body = {
            "page_size": 100,
        }

        if start_cursor is not None:
            body["start_cursor"] = start_cursor

        response = httpx.post(
            (
                f"{NOTION_API_URL}"
                f"/data_sources/"
                f"{STUDY_DATA_SOURCE_ID}"
                f"/query"
            ),
            headers=headers(),
            json=body,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

        pages.extend(
            data["results"]
        )

        if not data["has_more"]:
            break

        start_cursor = data["next_cursor"]

    return pages