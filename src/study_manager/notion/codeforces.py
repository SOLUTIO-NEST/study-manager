import os

import httpx
from dotenv import load_dotenv

from study_manager.judges.codeforces import (
    CodeforcesProblem,
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

CODEFORCES_DATA_SOURCE_ID = os.environ[
    "NOTION_CODEFORCES_DATA_SOURCE_ID"
]

STUDY_RELATION_PROPERTY = (
    "📚 스터디 데이터베이스"
)

_template_id_cache: str | None = None


# ----------------------------------------------------------------------
# Metadata
# ----------------------------------------------------------------------


def _problem_id(
    problem: CodeforcesProblem,
) -> str:
    prefix = (
        "G-"
        if problem.is_gym
        else ""
    )

    return (
        f"{prefix}"
        f"{problem.contest_id}"
        f"{problem.index}"
    )


def _build_metadata_properties(
    problem: CodeforcesProblem,
) -> dict:
    return {
        "이름": {
            "title": [
                {
                    "text": {
                        "content": (
                            problem.title
                        ),
                    }
                }
            ]
        },

        "문제 번호": {
            "rich_text": [
                {
                    "text": {
                        "content": (
                            _problem_id(
                                problem
                            )
                        ),
                    }
                }
            ]
        },

        "레이팅": {
            "number": problem.rating,
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
# Template
# ----------------------------------------------------------------------


def _get_template_id() -> str:
    global _template_id_cache

    if _template_id_cache is not None:
        return _template_id_cache

    templates = []
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
                f"/data_sources/"
                f"{CODEFORCES_DATA_SOURCE_ID}"
                f"/templates"
            ),
            headers=headers(),
            params=params,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

        # Notion 응답 형태 변화에 조금 더 안전하게 대응
        items = (
            data.get("templates")
            or data.get("results")
            or []
        )

        templates.extend(
            items
        )

        if not data.get(
            "has_more",
            False,
        ):
            break

        start_cursor = data.get(
            "next_cursor"
        )

    if not templates:
        raise ValueError(
            "Codeforces 데이터베이스에 "
            "템플릿이 없습니다."
        )

    default_templates = [
        template
        for template in templates
        if template.get(
            "is_default",
            False,
        )
    ]

    if default_templates:
        template = (
            default_templates[0]
        )

    elif len(templates) == 1:
        template = templates[0]

    else:
        raise ValueError(
            "Codeforces 데이터베이스에 "
            "템플릿이 여러 개 있지만 "
            "기본 템플릿을 찾을 수 없습니다."
        )

    _template_id_cache = (
        template["id"]
    )

    return _template_id_cache


# ----------------------------------------------------------------------
# Find / create / update
# ----------------------------------------------------------------------


def find_problem(
    problem_id: str,
) -> dict | None:
    response = httpx.post(
        (
            f"{NOTION_API_URL}"
            f"/data_sources/"
            f"{CODEFORCES_DATA_SOURCE_ID}"
            f"/query"
        ),
        headers=headers(),
        json={
            "filter": {
                "property": "문제 번호",
                "rich_text": {
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
    problem: CodeforcesProblem,
) -> dict:
    response = httpx.post(
        f"{NOTION_API_URL}/pages",
        headers=headers(),
        json={
            "parent": {
                "type": "data_source_id",
                "data_source_id": (
                    CODEFORCES_DATA_SOURCE_ID
                ),
            },

            "template": {
                "type": "template_id",
                "template_id": (
                    _get_template_id()
                ),
            },

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
    problem: CodeforcesProblem,
) -> dict:
    response = httpx.patch(
        f"{NOTION_API_URL}/pages/{page_id}",
        headers=headers(),
        json={
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
    problem: CodeforcesProblem,
) -> tuple[dict, bool]:
    problem_id = _problem_id(
        problem
    )

    existing = find_problem(
        problem_id
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
            f"{CODEFORCES_DATA_SOURCE_ID}"
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
                    properties[
                        "문제 번호"
                    ]["id"]
                ),
                "visible": True,
                "width": 90,
            },
            {
                "property_id": (
                    properties[
                        "레이팅"
                    ]["id"]
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
                CODEFORCES_DATA_SOURCE_ID
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
            CODEFORCES_DATA_SOURCE_ID
        ),
    )

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

    if view_id is None:
        return create_view(
            database_id=database_id,
            data_source_id=(
                CODEFORCES_DATA_SOURCE_ID
            ),
            name=f"코포 {problem_count}",
            filter_data=filter_data,
            sorts=sorts,
            configuration=(
                _get_view_configuration()
            ),
            position="end",
        )

    return update_view(
        view_id=view_id,
        name=f"코포 {problem_count}",
        filter_data=filter_data,
        sorts=sorts,
    )


def sync_study_view(
    study_page_id: str,
    expected_problem_page_id: str,
) -> dict:
    wait_for_relation(
        data_source_id=(
            CODEFORCES_DATA_SOURCE_ID
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
            "Codeforces View를 "
            "동기화하지 못했습니다."
        )

    return view