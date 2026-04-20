def test_notes_core_flow(admin_login):
    client = admin_login

    notebook = client.post("/api/notebooks", json={"name": "Test NB", "description": "d", "icon": "N", "sort_order": 0})
    assert notebook.status_code == 200
    nb_id = notebook.json()["id"]

    note = client.post(
        "/api/notes",
        json={
            "notebook_id": nb_id,
            "title": "hello",
            "content": "world",
            "note_type": "doc",
        },
    )
    assert note.status_code == 200
    created_note = note.json()
    note_id = created_note.get("id")
    if note_id is None:
        listing_after_create = client.get("/api/notes")
        assert listing_after_create.status_code == 200
        note_id = next(x["id"] for x in listing_after_create.json() if x.get("title") == "hello")

    fetched = client.get(f"/api/notes/{note_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "hello"

    listing = client.get("/api/notes")
    assert listing.status_code == 200
    assert any(x["id"] == note_id for x in listing.json())
