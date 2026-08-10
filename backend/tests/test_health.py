def test_health(app_env):
    resp = app_env.client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"state": "ok"}
