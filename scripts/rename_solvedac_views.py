import argparse
import re

import httpx

from study_manager.notion.api import (
    NOTION_API_URL,
    headers,
)
from study_manager.notion.solvedac import (
    SOLVEDAC_DATA_SOURCE_ID,
)


def rename_views(
    apply: bool = False,
) -> None:
    views = []
    start_cursor = None

    while True:
        params = {
            "data_source_id": SOLVEDAC_DATA_SOURCE_ID,
            "page_size": 100,
        }

        if start_cursor is not None:
            params["start_cursor"] = start_cursor

        response = httpx.get(
            f"{NOTION_API_URL}/views",
            headers=headers(),
            params=params,
            timeout=10.0,
        )

        response.raise_for_status()

        data = response.json()

        views.extend(
            data["results"]
        )

        if not data["has_more"]:
            break

        start_cursor = data["next_cursor"]

    changed = 0

    for item in views:
        response = httpx.get(
            f"{NOTION_API_URL}/views/{item['id']}",
            headers=headers(),
            timeout=10.0,
        )

        response.raise_for_status()

        view = response.json()

        if view["data_source_id"] != SOLVEDAC_DATA_SOURCE_ID:
            raise ValueError(
                "다른 Data Source의 View가 조회되었습니다."
            )

        name = view["name"]

        if re.fullmatch(
            r"(?:백준|solved\.ac)(?: [0-9]+)?",
            name,
        ) is None:
            continue

        new_name = re.sub(
            r"^(?:백준|solved\.ac)",
            "솔브닥",
            name,
        )

        print(
            f"{view['id']}: "
            f"{name} -> {new_name}"
        )

        if apply:
            response = httpx.patch(
                f"{NOTION_API_URL}/views/{view['id']}",
                headers=headers(),
                json={
                    "name": new_name,
                },
                timeout=10.0,
            )

            response.raise_for_status()

        changed += 1

    action = (
        "변경 완료"
        if apply
        else "변경 예정"
    )

    print(
        f"{action}: {changed}개 "
        f"(확인한 View: {len(views)}개)"
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "기존 백준·solved.ac View 이름을 솔브닥으로 변경합니다."
        ),
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제로 View 이름을 변경합니다.",
    )

    args = parser.parse_args()

    rename_views(
        apply=args.apply,
    )


if __name__ == "__main__":
    main()
