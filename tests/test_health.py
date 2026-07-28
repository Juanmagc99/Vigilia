def test_health_check_remains_public(
    client,
    configured_api_security,
) -> None:
    res = client.get("/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "Vigilia", "env": "local"}
