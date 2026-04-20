def test_app_create_and_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    payload = r.json()
    assert payload["ok"] is True
    assert "version" in payload
    assert "db" in payload
