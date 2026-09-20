import os

import httpx
from dotenv import load_dotenv

from study_manager.judges.boj import (
    BojProblem,
)
from study_manager.notion.api import (
    NOTION_API_URL,
    headers,
)
from study_manager.notion.relations import (
    add_relation,
    query_pages_by_relation,
    wait_for_relation,
)
from study_manager.notion.study import (
    get_problem_database_id,
)
from study_manager.notion.views import (
    create_view,
    delete_view,
    find_view_id,
    update_view,
)


load_dotenv()

BOJ_DATA_SOURCE_ID = os.environ[
    "NOTION_BOJ_DATA_SOURCE_ID"
]

STUDY_RELATION_PROPERTY = (
    "📚 스터디 데이터베이스"
)

_custom_emoji_cache: dict[str, str] = {}


# ----------------------------------------------------------------------
# Marker / icon
# ----------------------------------------------------------------------


def get_marker_name(
    problem: BojProblem,
) -> str:
    if (
        problem.sprout
        and 1 <= problem.level <= 5
    ):
        return f"s{problem.level}"

    if problem.level == 0:
        if problem.is_solvable:
            return "00"

        return "nr"

    if problem.level == 31:
        return "31"

    if 1 <= problem.level <= 30:
        return f"{problem.level:02d}"

    raise ValueError(
        "아이콘을 결정할 수 없는 "
        f"BOJ 난이도입니다: {problem.level}"
    )


def _load_custom_emojis() -> None:
    start_cursor = None

    while True:
        params = {
            "page_size": 100,
        }

        if start_cursor is not None:
            params["start_cursor"] = start_cursor

        response = httpx.get(
            f"{NOTION_API_URL}/custom_emojis",
            headers=headers(),
            params=params,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

        for emoji in data["results"]:
            _custom_emoji_cache[
                emoji["name"]
            ] = emoji["id"]

        if not data["has_more"]:
            break

        start_cursor = data["next_cursor"]


def _get_custom_emoji_id(
    name: str,
) -> str:
    if not _custom_emoji_cache:
        _load_custom_emojis()

    emoji_id = _custom_emoji_cache.get(
        name
    )

    if emoji_id is None:
        raise ValueError(
            "Notion custom emoji "
            f"'{name}'을 찾을 수 없습니다."
        )

    return emoji_id


def _get_problem_icon(
    problem: BojProblem,
) -> dict:
    marker_name = get_marker_name(
        problem
    )

    emoji_id = _get_custom_emoji_id(
        marker_name
    )

    return {
        "type": "custom_emoji",
        "custom_emoji": {
            "id": emoji_id,
        },
    }


# ----------------------------------------------------------------------
# Metadata
# ----------------------------------------------------------------------


def _build_metadata_properties(
    problem: BojProblem,
) -> dict:
    return {
        "이름": {
            "title": [
                {
                    "text": {
                        "content": problem.title,
                    }
                }
            ]
        },

        "문제 번호": {
            "number": problem.problem_id,
        },

        "티어": {
            "select": (
                {
                    "name": problem.tier,
                }
                if problem.tier is not None
                else None
            ),
        },

        "태그": {
            "multi_select": [
                {
                    "name": tag,
                }
                for tag in problem.tags
            ]
        },

        "문제 링크": {
            "url": problem.url,
        },
    }


# ----------------------------------------------------------------------
# Find / create / update
# ----------------------------------------------------------------------


def find_problem(
    problem_id: int,
) -> dict | None:
    response = httpx.post(
        (
            f"{NOTION_API_URL}"
            f"/data_sources/"
            f"{BOJ_DATA_SOURCE_ID}"
            f"/query"
        ),
        headers=headers(),
        json={
            "filter": {
                "property": "문제 번호",
                "number": {
                    "equals": problem_id,
                },
            },
            "page_size": 1,
        },
        timeout=10.0,
    )

    response.raise_for_status()

    results = response.json()["results"]

    if not results:
        return None

    return results[0]


def create_problem(
    problem: BojProblem,
) -> dict:
    response = httpx.post(
        f"{NOTION_API_URL}/pages",
        headers=headers(),
        json={
            "parent": {
                "type": "data_source_id",
                "data_source_id": (
                    BOJ_DATA_SOURCE_ID
                ),
            },

            "template": {
                "type": "default",
            },

            "icon": _get_problem_icon(
                problem
            ),

            "properties": (
                _build_metadata_properties(
                    problem
                )
            ),
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


def update_problem_metadata(
    page_id: str,
    problem: BojProblem,
) -> dict:
    response = httpx.patch(
        f"{NOTION_API_URL}/pages/{page_id}",
        headers=headers(),
        json={
            "icon": _get_problem_icon(
                problem
            ),

            "properties": (
                _build_metadata_properties(
                    problem
                )
            ),
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


def save_problem(
    problem: BojProblem,
) -> tuple[dict, bool]:
    existing = find_problem(
        problem.problem_id
    )

    if existing is not None:
        updated = update_problem_metadata(
            existing["id"],
            problem,
        )

        return updated, False

    created = create_problem(
        problem
    )

    return created, True


# ----------------------------------------------------------------------
# Study relation
# ----------------------------------------------------------------------


def add_study_relation(
    problem_page_id: str,
    study_page_id: str,
) -> dict:
    return add_relation(
        page_id=problem_page_id,
        property_name=(
            STUDY_RELATION_PROPERTY
        ),
        target_page_id=study_page_id,
    )


# ----------------------------------------------------------------------
# Study view
# ----------------------------------------------------------------------


def _get_view_configuration() -> dict:
    response = httpx.get(
        (
            f"{NOTION_API_URL}"
            f"/data_sources/"
            f"{BOJ_DATA_SOURCE_ID}"
        ),
        headers=headers(),
        timeout=10.0,
    )

    response.raise_for_status()

    properties = (
        response.json()["properties"]
    )

    return {
        "type": "table",

        "properties": [
            {
                "property_id": (
                    properties["이름"]["id"]
                ),
                "visible": True,
                "width": 260,
            },
            {
                "property_id": (
                    properties["문제 번호"]["id"]
                ),
                "visible": True,
                "width": 90,
            },
            {
                "property_id": (
                    properties["티어"]["id"]
                ),
                "visible": True,
                "width": 80,
            },
            {
                "property_id": (
                    properties[
                        STUDY_RELATION_PROPERTY
                    ]["id"]
                ),
                "visible": False,
            },
            {
                "property_id": (
                    properties["태그"]["id"]
                ),
                "visible": False,
            },
            {
                "property_id": (
                    properties[
                        "문제 링크"
                    ]["id"]
                ),
                "visible": False,
            },
        ],

        "wrap_cells": False,
    }


def rebuild_study_view(
    study_page_id: str,
) -> dict | None:
    problem_pages = (
        query_pages_by_relation(
            data_source_id=(
                BOJ_DATA_SOURCE_ID
            ),
            property_name=(
                STUDY_RELATION_PROPERTY
            ),
            target_page_id=(
                study_page_id
            ),
        )
    )

    problem_count = len(
        problem_pages
    )

    database_id = (
        get_problem_database_id(
            study_page_id
        )
    )

    view_id = find_view_id(
        database_id=database_id,
        data_source_id=(
            BOJ_DATA_SOURCE_ID
        ),
    )

    # 문제가 하나도 없으면
    # BOJ View를 제거한다.
    #
    # 단, 마지막 View라서 삭제할 수 없는 경우
    # delete_view()가 그냥 남겨둔다.
    if problem_count == 0:
        if view_id is not None:
            delete_view(
                view_id=view_id,
                database_id=database_id,
            )

        return None

    filter_data = {
        "property": (
            STUDY_RELATION_PROPERTY
        ),
        "relation": {
            "contains": study_page_id,
        },
    }

    sorts = [
        {
            "property": "문제 번호",
            "direction": "ascending",
        },
    ]

    # 과거에 BOJ View가 삭제됐는데
    # 나중에 BOJ 문제가 추가된 경우
    if view_id is None:
        return create_view(
            database_id=database_id,
            data_source_id=(
                BOJ_DATA_SOURCE_ID
            ),
            name=f"백준 {problem_count}",
            filter_data=filter_data,
            sorts=sorts,
            configuration=(
                _get_view_configuration()
            ),

            # BOJ는 항상 앞쪽
            position="start",
        )

    return update_view(
        view_id=view_id,
        name=f"백준 {problem_count}",
        filter_data=filter_data,
        sorts=sorts,
        configuration=_get_view_configuration(),
    )


def sync_study_view(
    study_page_id: str,
    expected_problem_page_id: str,
) -> dict:
    wait_for_relation(
        data_source_id=(
            BOJ_DATA_SOURCE_ID
        ),
        property_name=(
            STUDY_RELATION_PROPERTY
        ),
        target_page_id=study_page_id,
        expected_page_id=(
            expected_problem_page_id
        ),
    )

    view = rebuild_study_view(
        study_page_id
    )

    if view is None:
        raise RuntimeError(
            "BOJ View를 동기화하지 못했습니다."
        )

    return view