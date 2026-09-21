import os

import httpx
from dotenv import load_dotenv

from study_manager.judges.programmers import (
    ProgrammersProblem,
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

PROGRAMMERS_DATA_SOURCE_ID = os.environ[
    "NOTION_PROGRAMMERS_DATA_SOURCE_ID"
]

STUDY_RELATION_PROPERTY = (
    "📚 스터디 데이터베이스"
)

_template_id_cache: str | None = None


# ----------------------------------------------------------------------
# Metadata
# ----------------------------------------------------------------------


def _build_metadata_properties(
    problem: ProgrammersProblem,
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

        "레벨": {
            "select": (
                {
                    "name": f"Lv. {problem.level}",
                }
                if problem.level is not None
                else None
            ),
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
                f"{PROGRAMMERS_DATA_SOURCE_ID}"
                f"/templates"
            ),
            headers=headers(),
            params=params,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

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
            "프로그래머스 데이터베이스에 "
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
        template = default_templates[0]

    elif len(templates) == 1:
        template = templates[0]

    else:
        raise ValueError(
            "프로그래머스 데이터베이스에 "
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
    problem_id: int,
) -> dict | None:
    response = httpx.post(
        (
            f"{NOTION_API_URL}"
            f"/data_sources/"
            f"{PROGRAMMERS_DATA_SOURCE_ID}"
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
    problem: ProgrammersProblem,
) -> dict:
    response = httpx.post(
        f"{NOTION_API_URL}/pages",
        headers=headers(),
        json={
            "parent": {
                "type": "data_source_id",
                "data_source_id": (
                    PROGRAMMERS_DATA_SOURCE_ID
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
    problem: ProgrammersProblem,
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
    problem: ProgrammersProblem,
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
            f"{PROGRAMMERS_DATA_SOURCE_ID}"
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
                    properties["레벨"]["id"]
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
                PROGRAMMERS_DATA_SOURCE_ID
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
            PROGRAMMERS_DATA_SOURCE_ID
        ),
    )

    # 이 스터디에서 프머 문제를
    # 하나도 풀지 않았으면 View 제거
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

    # 기존 스터디에 프머 View가 없으면
    # 새 탭 생성
    if view_id is None:
        return create_view(
            database_id=database_id,
            data_source_id=(
                PROGRAMMERS_DATA_SOURCE_ID
            ),
            name=f"프머 {problem_count}",
            filter_data=filter_data,
            sorts=sorts,
            configuration=(
                _get_view_configuration()
            ),
            position="end",
        )

    # 이미 있으면 이름/필터/정렬/너비 갱신
    return update_view(
        view_id=view_id,
        name=f"프머 {problem_count}",
        filter_data=filter_data,
        sorts=sorts,
        configuration=(
            _get_view_configuration()
        ),
    )


def sync_study_view(
    study_page_id: str,
    expected_problem_page_id: str,
) -> dict:
    wait_for_relation(
        data_source_id=(
            PROGRAMMERS_DATA_SOURCE_ID
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
            "프로그래머스 View를 "
            "동기화하지 못했습니다."
        )

    return view