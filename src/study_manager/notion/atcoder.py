import os

import httpx
from dotenv import load_dotenv

from study_manager.judges.atcoder import (
    AtCoderProblem,
)
from study_manager.network import (
    NOTION_GATE,
    request,
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

ATCODER_DATA_SOURCE_ID = os.getenv(
    "NOTION_ATCODER_DATA_SOURCE_ID",
    "",
).strip()

STUDY_RELATION_PROPERTY = (
    "📚 스터디 데이터베이스"
)


def _get_data_source_id() -> str:
    if not ATCODER_DATA_SOURCE_ID:
        raise ValueError(
            "AtCoder 데이터베이스 설정이 없습니다. "
            "NOTION_ATCODER_DATA_SOURCE_ID를 설정하세요."
        )

    return ATCODER_DATA_SOURCE_ID


def _build_metadata_properties(
    problem: AtCoderProblem,
) -> dict:
    properties = {
        "이름": {
            "title": [
                {"text": {"content": problem.title}},
            ],
        },
        "문제 번호": {
            "rich_text": [
                {"text": {"content": problem.problem_id}},
            ],
        },
        "문제 링크": {
            "url": problem.url,
        },
    }

    # 아직 난이도가 없으면 기존 값을 덮어쓰지 않는다.
    if problem.difficulty is not None:
        properties["난이도"] = {
            "number": problem.difficulty,
        }

    return properties


def find_problem(
    problem_id: str,
) -> dict | None:
    data_source_id = _get_data_source_id()
    response = request(
        NOTION_GATE,
        httpx.post,
        f"{NOTION_API_URL}/data_sources/{data_source_id}/query",
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

    return results[0] if results else None


def create_problem(
    problem: AtCoderProblem,
) -> dict:
    response = request(
        NOTION_GATE,
        httpx.post,
        f"{NOTION_API_URL}/pages",
        headers=headers(),
        json={
            "parent": {
                "type": "data_source_id",
                "data_source_id": _get_data_source_id(),
            },
            "properties": _build_metadata_properties(
                problem
            ),
        },
        timeout=10.0,
    )

    response.raise_for_status()
    return response.json()


def update_problem_metadata(
    page_id: str,
    problem: AtCoderProblem,
    preserve_identity: bool = False,
) -> dict:
    properties = _build_metadata_properties(
        problem
    )

    if preserve_identity:
        properties.pop("문제 번호")
        properties.pop("문제 링크")

    response = request(
        NOTION_GATE,
        httpx.patch,
        f"{NOTION_API_URL}/pages/{page_id}",
        headers=headers(),
        json={
            "properties": properties,
        },
        timeout=10.0,
    )

    response.raise_for_status()
    return response.json()


def save_problem(
    problem: AtCoderProblem,
) -> tuple[dict, bool]:
    existing = find_problem(
        problem.problem_id
    )

    if existing is not None:
        updated = update_problem_metadata(
            existing["id"],
            problem,
            preserve_identity=True,
        )

        return updated, False

    created = create_problem(
        problem
    )

    return created, True


def add_study_relation(
    problem_page_id: str,
    study_page_id: str,
) -> dict:
    page = add_relation(
        page_id=problem_page_id,
        property_name=STUDY_RELATION_PROPERTY,
        target_page_id=study_page_id,
    )

    wait_for_relation(
        data_source_id=_get_data_source_id(),
        property_name=STUDY_RELATION_PROPERTY,
        target_page_id=study_page_id,
        expected_page_id=problem_page_id,
    )

    return page


def _get_view_configuration(
    data_source_id: str,
) -> dict:
    response = request(
        NOTION_GATE,
        httpx.get,
        f"{NOTION_API_URL}/data_sources/{data_source_id}",
        headers=headers(),
        timeout=10.0,
    )

    response.raise_for_status()
    properties = response.json()["properties"]

    columns = [
        {
            "property_id": properties[name]["id"],
            "visible": True,
            "width": width,
        }
        for name, width in [
            ("이름", 260),
            ("문제 번호", 145),
            ("난이도", 80),
        ]
    ]

    columns.extend(
        {
            "property_id": properties[name]["id"],
            "visible": False,
        }
        for name in [
            STUDY_RELATION_PROPERTY,
            "문제 링크",
        ]
    )

    return {
        "type": "table",
        "properties": columns,
        "wrap_cells": False,
    }


def rebuild_study_view(
    study_page_id: str,
) -> dict | None:
    data_source_id = ATCODER_DATA_SOURCE_ID

    if not data_source_id:
        return None

    problem_pages = query_pages_by_relation(
        data_source_id=data_source_id,
        property_name=STUDY_RELATION_PROPERTY,
        target_page_id=study_page_id,
    )

    database_id = get_problem_database_id(
        study_page_id
    )

    view_id = find_view_id(
        database_id=database_id,
        data_source_id=data_source_id,
    )

    if not problem_pages:
        if view_id is not None:
            delete_view(
                view_id=view_id,
                database_id=database_id,
            )

        return None

    name = f"AtCoder {len(problem_pages)}"
    filter_data = {
        "property": STUDY_RELATION_PROPERTY,
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
    configuration = _get_view_configuration(
        data_source_id
    )

    if view_id is None:
        return create_view(
            database_id=database_id,
            data_source_id=data_source_id,
            name=name,
            filter_data=filter_data,
            sorts=sorts,
            configuration=configuration,
        )

    return update_view(
        view_id=view_id,
        name=name,
        filter_data=filter_data,
        sorts=sorts,
        configuration=configuration,
    )
