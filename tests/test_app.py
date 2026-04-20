import importlib
from unittest.mock import MagicMock
import pytest
import requests
import psycopg2
import prometheus_client

@pytest.fixture
def app_module(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth-service")
    prometheus_client.REGISTRY = prometheus_client.CollectorRegistry()

    fake_pool = MagicMock()
    monkeypatch.setattr("psycopg2.pool.SimpleConnectionPool", lambda *args, **kwargs: fake_pool)

    import app
    importlib.reload(app)
    return app


@pytest.fixture
def client(app_module):
    return app_module.app.test_client()


def mock_auth_ok(app_module, monkeypatch):
    response = MagicMock()
    response.status_code = 200
    monkeypatch.setattr(app_module.requests, "get", lambda *args, **kwargs: response)


def auth_headers():
    return {"Authorization": "Bearer fake-token"}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_require_auth_without_header_returns_401(client):
    response = client.post("/rules", json={"flag_name": "f1", "rules": {"type": "PERCENTAGE", "value": 50}})
    assert response.status_code == 401
    assert response.get_json()["error"] == "Authorization header obrigatório"


def test_require_auth_invalid_key_returns_401(client, app_module, monkeypatch):
    response_mock = MagicMock()
    response_mock.status_code = 401
    monkeypatch.setattr(app_module.requests, "get", lambda *args, **kwargs: response_mock)

    response = client.post(
        "/rules",
        headers=auth_headers(),
        json={"flag_name": "f1", "rules": {"type": "PERCENTAGE", "value": 50}},
    )
    assert response.status_code == 401
    assert response.get_json()["error"] == "Chave de API inválida"


def test_require_auth_timeout_returns_504(client, app_module, monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(app_module.requests, "get", raise_timeout)

    response = client.post(
        "/rules",
        headers=auth_headers(),
        json={"flag_name": "f1", "rules": {"type": "PERCENTAGE", "value": 50}},
    )
    assert response.status_code == 504


def test_require_auth_request_exception_returns_503(client, app_module, monkeypatch):
    def raise_error(*args, **kwargs):
        raise requests.exceptions.RequestException("boom")

    monkeypatch.setattr(app_module.requests, "get", raise_error)

    response = client.post(
        "/rules",
        headers=auth_headers(),
        json={"flag_name": "f1", "rules": {"type": "PERCENTAGE", "value": 50}},
    )
    assert response.status_code == 503


def test_create_rule_success(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.fetchone.return_value = {
        "id": 1,
        "flag_name": "f1",
        "is_enabled": True,
        "rules": {"type": "PERCENTAGE", "value": 50},
    }

    response = client.post(
        "/rules",
        headers=auth_headers(),
        json={"flag_name": "f1", "rules": {"type": "PERCENTAGE", "value": 50}},
    )

    assert response.status_code == 201
    assert response.get_json()["flag_name"] == "f1"
    conn.commit.assert_called_once()
    cur.close.assert_called_once()
    app_module.pool.putconn.assert_called_once_with(conn)


def test_create_rule_missing_fields_returns_400(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    response = client.post("/rules", headers=auth_headers(), json={"flag_name": "f1"})
    assert response.status_code == 400


def test_create_rule_duplicate_returns_409(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.execute.side_effect = psycopg2.IntegrityError()

    response = client.post(
        "/rules",
        headers=auth_headers(),
        json={"flag_name": "f1", "rules": {"type": "USER_LIST", "values": ["u1"]}},
    )

    assert response.status_code == 409
    conn.rollback.assert_called_once()


def test_create_rule_unexpected_error_returns_500(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.execute.side_effect = Exception("db error")

    response = client.post(
        "/rules",
        headers=auth_headers(),
        json={"flag_name": "f1", "rules": {"type": "USER_LIST", "values": ["u1"]}},
    )

    assert response.status_code == 500
    conn.rollback.assert_called_once()


def test_get_rule_success(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.fetchone.return_value = {
        "id": 1,
        "flag_name": "f1",
        "is_enabled": True,
        "rules": {"type": "PERCENTAGE", "value": 50},
    }

    response = client.get("/rules/f1", headers=auth_headers())

    assert response.status_code == 200
    assert response.get_json()["flag_name"] == "f1"


def test_get_rule_not_found_returns_404(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.fetchone.return_value = None

    response = client.get("/rules/f1", headers=auth_headers())
    assert response.status_code == 404


def test_get_rule_error_returns_500(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.execute.side_effect = Exception("db error")

    response = client.get("/rules/f1", headers=auth_headers())
    assert response.status_code == 500


def test_update_rule_without_body_returns_400(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    response = client.put("/rules/f1", headers=auth_headers(), json=None)
    assert response.status_code == 400


def test_update_rule_without_valid_fields_returns_400(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    response = client.put("/rules/f1", headers=auth_headers(), json={"foo": "bar"})
    assert response.status_code == 400


def test_update_rule_success(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.rowcount = 1
    cur.fetchone.return_value = {
        "id": 1,
        "flag_name": "f1",
        "is_enabled": False,
        "rules": {"type": "PERCENTAGE", "value": 10},
    }

    response = client.put(
        "/rules/f1",
        headers=auth_headers(),
        json={"is_enabled": False, "rules": {"type": "PERCENTAGE", "value": 10}},
    )

    assert response.status_code == 200
    assert response.get_json()["is_enabled"] is False
    conn.commit.assert_called_once()


def test_update_rule_not_found_returns_404(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.rowcount = 0

    response = client.put(
        "/rules/f1",
        headers=auth_headers(),
        json={"is_enabled": False},
    )

    assert response.status_code == 404


def test_update_rule_error_returns_500(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.execute.side_effect = Exception("db error")

    response = client.put(
        "/rules/f1",
        headers=auth_headers(),
        json={"is_enabled": False},
    )

    assert response.status_code == 500
    conn.rollback.assert_called_once()


def test_delete_rule_success(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.rowcount = 1

    response = client.delete("/rules/f1", headers=auth_headers())

    assert response.status_code == 204
    conn.commit.assert_called_once()


def test_delete_rule_not_found_returns_404(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.rowcount = 0

    response = client.delete("/rules/f1", headers=auth_headers())
    assert response.status_code == 404


def test_delete_rule_error_returns_500(client, app_module, monkeypatch):
    mock_auth_ok(app_module, monkeypatch)

    conn = MagicMock()
    cur = MagicMock()
    app_module.pool.getconn.return_value = conn
    conn.cursor.return_value = cur
    cur.execute.side_effect = Exception("db error")

    response = client.delete("/rules/f1", headers=auth_headers())
    assert response.status_code == 500
    conn.rollback.assert_called_once()
