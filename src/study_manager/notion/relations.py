import time

import httpx

from study_manager.notion.api import (
    NOTION_API_URL,
    headers,
)


def _get_relation_property_id(
    page_id: str,
    property_name: str,
) -> str:
    response = httpx.get(
        f"{NOTION_API_URL}/pages/{page_id}",
        headers=headers(),
        timeout=10.0,
    )

    response.raise_for_status()

    page = response.json()

    prop = page["properties"].get(
        property_name
    )

    if prop is None:
        raise ValueError(
            f"'{property_name}' 속성이 없습니다."
        )

    if prop["type"] != "relation":
        raise ValueError(
            f"'{property_name}' 속성이 "
            "relation 타입이 아닙니다."
        )

    return prop["id"]


def get_relation_ids(
    page_id: str,
    property_name: str,
) -> list[str]:
    property_id = (
        _get_relation_property_id(
            page_id,
            property_name,
        )
    )

    relation_ids = []
    start_cursor = None

    while True:
        params = {}

        if start_cursor is not None:
            params["start_cursor"] = (
                start_cursor
            )

        response = httpx.get(
            (
                f"{NOTION_API_URL}"
                f"/pages/{page_id}"
                f"/properties/{property_id}"
            ),
            headers=headers(),
            params=params,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

        for item in data["results"]:
            relation = item.get(
                "relation"
            )

            if relation is not None:
                relation_ids.append(
                    relation["id"]
                )

        if not data["has_more"]:
            break

        start_cursor = (
            data["next_cursor"]
        )

    return relation_ids


def add_relation(
    page_id: str,
    property_name: str,
    target_page_id: str,
) -> dict:
    relation_ids = get_relation_ids(
        page_id,
        property_name,
    )

    if target_page_id in relation_ids:
        response = httpx.get(
            f"{NOTION_API_URL}/pages/{page_id}",
            headers=headers(),
            timeout=10.0,
        )

        response.raise_for_status()

        return response.json()

    relation_ids.append(
        target_page_id
    )

    response = httpx.patch(
        f"{NOTION_API_URL}/pages/{page_id}",
        headers=headers(),
        json={
            "properties": {
                property_name: {
                    "relation": [
                        {
                            "id": relation_id,
                        }
                        for relation_id
                        in relation_ids
                    ]
                }
            }
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


def query_pages_by_relation(
    data_source_id: str,
    property_name: str,
    target_page_id: str,
) -> list[dict]:
    pages = []
    start_cursor = None

    while True:
        body = {
            "filter": {
                "property": property_name,
                "relation": {
                    "contains": (
                        target_page_id
                    ),
                },
            },
            "page_size": 100,
        }

        if start_cursor is not None:
            body["start_cursor"] = (
                start_cursor
            )

        response = httpx.post(
            (
                f"{NOTION_API_URL}"
                f"/data_sources/"
                f"{data_source_id}"
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

        start_cursor = (
            data["next_cursor"]
        )

    return pages


def wait_for_relation(
    data_source_id: str,
    property_name: str,
    target_page_id: str,
    expected_page_id: str,
    max_attempts: int = 6,
) -> int:
    for attempt in range(
        max_attempts
    ):
        pages = query_pages_by_relation(
            data_source_id,
            property_name,
            target_page_id,
        )

        if any(
            page["id"] == expected_page_id
            for page in pages
        ):
            return len(pages)

        if attempt < max_attempts - 1:
            delay = min(
                0.5 * (2 ** attempt),
                4.0,
            )

            time.sleep(delay)

    raise RuntimeError(
        "Notion relation 반영을 기다렸지만 "
        "새로 연결한 문제를 조회할 수 없습니다."
    )