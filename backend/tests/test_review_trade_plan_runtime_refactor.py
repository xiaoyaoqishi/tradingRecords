from services import utility_runtime


def test_review_session_and_legacy_review_routes(admin_login):
    client = admin_login

    created = client.post(
        "/api/review-sessions",
        json={
            "title": "session-refactor",
            "review_kind": "custom",
            "selection_basis": "manual selection",
            "review_goal": "verify runtime split",
            "tags": ["alpha", "beta"],
        },
    )
    assert created.status_code == 200
    session_id = created.json()["id"]

    legacy = client.get(f"/api/reviews/{session_id}")
    assert legacy.status_code == 200
    assert legacy.json()["id"] == session_id
    assert legacy.json()["tags"] == ["alpha", "beta"]

    updated = client.put(
        f"/api/reviews/{session_id}",
        json={"title": "legacy-updated", "tags": ["gamma"]},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "legacy-updated"
    assert updated.json()["tags"] == ["gamma"]

    session = client.get(f"/api/review-sessions/{session_id}")
    assert session.status_code == 200
    assert session.json()["title"] == "legacy-updated"
    assert session.json()["tags"] == ["gamma"]


def test_trade_plan_followup_review_session_route(admin_login):
    client = admin_login

    created = client.post(
        "/api/trade-plans",
        json={
            "title": "plan-refactor",
            "plan_date": "2026-04-27",
            "tags": ["followup"],
        },
    )
    assert created.status_code == 200
    plan_id = created.json()["id"]

    followup = client.post(f"/api/trade-plans/{plan_id}/create-followup-review-session")
    assert followup.status_code == 200
    assert followup.json()["tags"] == ["followup"]
    assert followup.json()["linked_trade_ids"] == []

    plan = client.get(f"/api/trade-plans/{plan_id}")
    assert plan.status_code == 200
    links = plan.json()["review_session_links"]
    assert len(links) == 1
    assert links[0]["note"] == "自动创建计划跟踪复盘"
    assert links[0]["review_session"]["selection_mode"] == "plan_linked"
    assert links[0]["review_session"]["tags_text"] == "followup"


def test_poem_and_upload_routes(admin_login, tmp_path):
    client = admin_login
    utility_runtime.UPLOAD_DIR = str(tmp_path)

    poem = client.get("/api/poem/daily")
    assert poem.status_code == 200
    poem_payload = poem.json()
    assert poem_payload["title"]
    assert poem_payload["text"]
    assert poem_payload["source"]

    upload = client.post(
        "/api/upload",
        files={"file": ("proof.png", b"split-runtime", "image/png")},
    )
    assert upload.status_code == 200
    upload_url = upload.json()["url"]
    assert upload_url.startswith("/api/uploads/")

    downloaded = client.get(upload_url)
    assert downloaded.status_code == 200
    assert downloaded.content == b"split-runtime"
