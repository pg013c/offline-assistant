from importlib.metadata import version

from fastapi.testclient import TestClient


def test_health_reports_ok_and_package_version(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": version("assistant")}


def test_health_is_documented_with_a_typed_response(client: TestClient) -> None:
    schema = client.get("/api/openapi.json").json()

    operation = schema["paths"]["/api/health"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/HealthResponse"}
    assert schema["components"]["schemas"]["HealthResponse"]["required"] == ["status", "version"]
