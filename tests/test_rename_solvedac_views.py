import httpx
import pytest

from scripts import rename_solvedac_views


@pytest.mark.parametrize("apply", [False, True])
def test_only_legacy_view_names_are_changed(
    monkeypatch,
    make_response,
    capsys,
    apply,
):
    views = {
        "legacy": "백준 3",
        "english": "solved.ac 4",
        "renamed": "솔브닥 5",
        "main": "Untitled",
        "custom": "백준 즐겨찾기",
    }

    def get(url, **kwargs):
        if url.endswith("/views"):
            assert kwargs["params"]["data_source_id"] == "test"

            return make_response(
                {
                    "results": [
                        {"id": view_id}
                        for view_id in views
                    ],
                    "has_more": False,
                },
            )

        view_id = url.rsplit("/", 1)[1]

        return make_response(
            {
                "id": view_id,
                "name": views[view_id],
                "data_source_id": "test",
            },
        )

    changes = []

    def patch(url, **kwargs):
        changes.append(kwargs["json"])

        view_id = url.rsplit("/", 1)[1]
        expected = {
            "legacy": "솔브닥 3",
            "english": "솔브닥 4",
        }

        assert kwargs["json"] == {"name": expected[view_id]}

        return make_response({})

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "patch", patch)

    rename_solvedac_views.rename_views(
        apply=apply,
    )

    assert len(changes) == 2 * int(apply)
    assert "2개" in capsys.readouterr().out
