def test_health_ok(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["services"]["postgres"] == "ok"
    assert payload["services"]["redis"] == "ok"
