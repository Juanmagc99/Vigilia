def test_protected_endpoint_requires_api_token(client, configured_api_security) -> None:
    response = client.get("/incidents")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_token"


def test_protected_endpoint_accepts_configured_api_token(
    client, configured_api_security, api_authorization_headers
) -> None:
    response = client.get("/incidents", headers=api_authorization_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_protected_endpoint_reports_missing_security_configuration(client) -> None:
    response = client.get("/incidents")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "api_security_not_configured"
