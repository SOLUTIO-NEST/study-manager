from study_manager.notion.boj import (
    rebuild_study_view as rebuild_boj_view,
)
from study_manager.notion.codeforces import (
    rebuild_study_view as rebuild_codeforces_view,
)
from study_manager.notion.study import (
    get_all_study_pages,
)


def get_page_title(
    page: dict,
) -> str:
    for prop in page["properties"].values():
        if prop.get("type") != "title":
            continue

        title = "".join(
            item.get(
                "plain_text",
                "",
            )
            for item in prop.get(
                "title",
                []
            )
        )

        if title:
            return title

    return page["id"]


def main():
    study_pages = (
        get_all_study_pages()
    )

    print(
        f"총 {len(study_pages)}개의 "
        "스터디를 동기화합니다."
    )
    print()

    success = 0
    failed = 0

    for study_page in study_pages:
        study_page_id = (
            study_page["id"]
        )

        study_name = get_page_title(
            study_page
        )

        try:
            # 1.
            # 코포 문제가 있으면 코포 View를
            # 먼저 생성/갱신한다.
            rebuild_codeforces_view(
                study_page_id
            )

            # 2.
            # BOJ를 생성/갱신하거나
            # BOJ 0 View를 제거한다.
            rebuild_boj_view(
                study_page_id
            )

            # 3.
            # 처음에 Codeforces 0 View가
            # 마지막 View라 삭제되지 못한 경우를
            # 한 번 더 정리한다.
            codeforces_view = (
                rebuild_codeforces_view(
                    study_page_id
                )
            )

            print(
                f"[성공] {study_name}"
            )

            if (
                codeforces_view
                is not None
            ):
                print(
                    "       "
                    "Codeforces View 있음"
                )

            success += 1

        except Exception as e:
            print(
                f"[실패] "
                f"{study_name}: {e}"
            )

            failed += 1

    print()
    print("--------------------")
    print(f"성공: {success}")
    print(f"실패: {failed}")


if __name__ == "__main__":
    main()