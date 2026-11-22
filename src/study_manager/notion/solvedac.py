import os

import httpx
from dotenv import load_dotenv

from study_manager.network import (
    NOTION_GATE,
    request,
)
from study_manager.judges.solvedac import (
    SolvedacProblem,
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
from study_manager.routing.problem_url import (
    Judge,
    parse_problem_url,
)


load_dotenv()

SOLVEDAC_DATA_SOURCE_ID = (
    os.getenv(
        "NOTION_SOLVEDAC_DATA_SOURCE_ID"
    )
    or os.environ[
        "NOTION_BOJ_DATA_SOURCE_ID"
    ]
)

STUDY_RELATION_PROPERTY = (
    "📚 스터디 데이터베이스"
)

_custom_emoji_cache: dict[str, str] = {}


# ----------------------------------------------------------------------
# Marker / icon
# ----------------------------------------------------------------------


def get_marker_name(
    problem: SolvedacProblem,
) -> str:
    if problem.level == 0:
        return (
            "nr"
            if problem.gives_no_rating
            else "00"
        )

    if problem.level == 31:
        return "31"

    if 1 <= problem.level <= 30:
        return f"{problem.level:02d}"

    raise ValueError(
        "아이콘을 결정할 수 없는 "
        f"solved.ac 난이도입니다: {problem.level}"
    )


def _load_custom_emojis() -> None:
    start_cursor = None

    while True:
        params = {
            "page_size": 100,
        }

        if start_cursor is not None:
            params["start_cursor"] = start_cursor

        response = request(
            NOTION_GATE,
            httpx.get,
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
    problem: SolvedacProblem,
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
    problem: SolvedacProblem,
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
    problem: SolvedacProblem,
) -> dict | None:
    # 기존 BOJ 페이지는 원래 번호로 찾고, 링크로 같은 문제인지 확인한다.
    # solved.ac에서는 같은 문제 번호에 여러 세부 번호가 있을 수 있다.
    boj_ids = {
        item["problemId"]
        for item in problem.judge_ids
        if item["ojId"] == "boj"
        and item["problemId"].isdigit()
    }

    problem_ids = {
        int(problem_id)
        for problem_id in boj_ids
    }

    problem_ids.add(
        problem.problem_id
    )

    filters = [
        {
            "property": "문제 링크",
            "url": {
                "equals": problem.url,
            },
        },
    ]

    filters.extend(
        [
            {
                "property": "문제 번호",
                "number": {
                    "equals": problem_id,
                },
            }
            for problem_id in sorted(problem_ids)
        ]
    )

    matches = {}
    start_cursor = None

    while True:
        body = {
            "filter": {
                "or": filters,
            },
            "page_size": 100,
        }

        if start_cursor is not None:
            body["start_cursor"] = start_cursor

        response = httpx.post(
            (
                f"{NOTION_API_URL}"
                f"/data_sources/"
                f"{SOLVEDAC_DATA_SOURCE_ID}"
                f"/query"
            ),
            headers=headers(),
            json=body,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

        for page in data["results"]:
            url = page["properties"]["문제 링크"]["url"]

            try:
                ref = parse_problem_url(
                    url or ""
                )
            except ValueError:
                raise ValueError(
                    "기존 문제의 링크를 확인할 수 없습니다. "
                    "Notion 문제 링크를 먼저 확인하세요: "
                    f"{page['id']}"
                )

            if (
                ref.judge == Judge.SOLVEDAC
                and ref.problem_id == problem.display_id
            ) or (
                ref.judge == Judge.BOJ
                and ref.problem_id in boj_ids
            ):
                matches[page["id"]] = page

        if not data["has_more"]:
            break

        start_cursor = data["next_cursor"]

    if len(matches) > 1:
        raise ValueError(
            "같은 solved.ac 문제에 해당하는 "
            "기존 Notion 페이지가 여러 개 있습니다. "
            "풀이와 Relation을 확인해 먼저 정리하세요: "
            + ", ".join(matches)
        )

    return next(
        iter(matches.values()),
        None,
    )


def create_problem(
    problem: SolvedacProblem,
) -> dict:
    response = httpx.post(
        f"{NOTION_API_URL}/pages",
        headers=headers(),
        json={
            "parent": {
                "type": "data_source_id",
                "data_source_id": (
                    SOLVEDAC_DATA_SOURCE_ID
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
    problem: SolvedacProblem,
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
            "icon": _get_problem_icon(
                problem
            ),

            "properties": properties,
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


def save_problem(
    problem: SolvedacProblem,
) -> tuple[dict, bool]:
    existing = find_problem(
        problem
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
            f"{SOLVEDAC_DATA_SOURCE_ID}"
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
                SOLVEDAC_DATA_SOURCE_ID
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
            SOLVEDAC_DATA_SOURCE_ID
        ),
    )

    # 문제가 하나도 없으면
    # solved.ac View를 제거한다.
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

    # 과거에 solved.ac View가 삭제됐는데
    # 나중에 solved.ac 문제가 추가된 경우
    if view_id is None:
        return create_view(
            database_id=database_id,
            data_source_id=(
                SOLVEDAC_DATA_SOURCE_ID
            ),
            name=f"솔브닥 {problem_count}",
            filter_data=filter_data,
            sorts=sorts,
            configuration=(
                _get_view_configuration()
            ),

            # solved.ac는 항상 앞쪽
            position="start",
        )

    return update_view(
        view_id=view_id,
        name=f"솔브닥 {problem_count}",
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
            SOLVEDAC_DATA_SOURCE_ID
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
            "solved.ac View를 동기화하지 못했습니다."
        )

    return view
