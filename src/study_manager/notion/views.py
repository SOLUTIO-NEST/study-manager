import time

import httpx

from study_manager.notion.api import (
    NOTION_API_URL,
    headers,
)


def _list_view_ids(
    **params,
) -> list[str]:
    view_ids = []
    start_cursor = None

    while True:
        query = {
            **params,
            "page_size": 100,
        }

        if start_cursor is not None:
            query["start_cursor"] = start_cursor

        response = httpx.get(
            f"{NOTION_API_URL}/views",
            headers=headers(),
            params=query,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

        view_ids.extend(
            view["id"]
            for view in data["results"]
        )

        if not data["has_more"]:
            break

        start_cursor = data["next_cursor"]

    return view_ids


def find_view_id(
    database_id: str,
    data_source_id: str,
) -> str | None:
    database_view_ids = set(
        _list_view_ids(
            database_id=database_id,
        )
    )

    data_source_view_ids = set(
        _list_view_ids(
            data_source_id=data_source_id,
        )
    )

    matched = (
        database_view_ids
        & data_source_view_ids
    )

    if not matched:
        return None

    if len(matched) > 1:
        raise ValueError(
            "동일한 data source를 사용하는 "
            "View가 여러 개 있습니다."
        )

    return matched.pop()


def create_view(
    database_id: str,
    data_source_id: str,
    name: str,
    filter_data: dict,
    sorts: list[dict],
    configuration: dict,
    position: str = "end",
) -> dict:
    response = httpx.post(
        f"{NOTION_API_URL}/views",
        headers=headers(),
        json={
            "database_id": database_id,
            "data_source_id": data_source_id,
            "name": name,
            "type": "table",
            "filter": filter_data,
            "sorts": sorts,
            "configuration": configuration,
            "position": {
                "type": position,
            },
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


def update_view(
    view_id: str,
    name: str,
    filter_data: dict,
    sorts: list[dict],
    configuration: dict | None = None,
) -> dict:
    body = {
        "name": name,
        "filter": filter_data,
        "sorts": sorts,
    }

    if configuration is not None:
        body["configuration"] = configuration

    response = httpx.patch(
        f"{NOTION_API_URL}/views/{view_id}",
        headers=headers(),
        json=body,
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


def delete_view(
    view_id: str,
    database_id: str,
    max_attempts: int = 6,
) -> dict | None:
    for attempt in range(max_attempts):
        view_ids = _list_view_ids(
            database_id=database_id,
        )

        # 이미 삭제되어 있으면 끝
        if view_id not in view_ids:
            return None

        # View가 하나뿐이면 지금은 삭제할 수 없다.
        # 직전에 다른 View를 만들었다면
        # Notion에 반영될 때까지 잠깐 기다린다.
        if len(view_ids) <= 1:
            if attempt < max_attempts - 1:
                time.sleep(
                    min(
                        0.5 * (2 ** attempt),
                        4.0,
                    )
                )
                continue

            return None

        response = httpx.delete(
            f"{NOTION_API_URL}/views/{view_id}",
            headers=headers(),
            timeout=10.0,
        )

        if response.is_success:
            if response.content:
                return response.json()

            return {}

        # 새 View 생성 직후 eventual consistency 때문에
        # 아직 마지막 View로 판단될 수 있음
        if (
            response.status_code == 400
            and attempt < max_attempts - 1
        ):
            time.sleep(
                min(
                    0.5 * (2 ** attempt),
                    4.0,
                )
            )
            continue

        raise RuntimeError(
            "Notion View 삭제 실패\n"
            f"status={response.status_code}\n"
            f"body={response.text}"
        )

    return None