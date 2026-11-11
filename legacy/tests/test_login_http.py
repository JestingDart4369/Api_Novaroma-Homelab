import pytest
from fastapi.testclient import TestClient
from app import auth
from app.db import engine
from sqlalchemy import event

# Never send startup email. Disposable database only.
import app.notifications
app.notifications.notify_startup_success = lambda: None
app.notifications.notify_startup_error = lambda error: None
@event.listens_for(engine, 'connect')
def fast_test_io(connection, _):
    connection.execute('PRAGMA synchronous=OFF')
from app.main import app
from app.deps import get_db


def test_login_limits_before_password_hash_and_ignores_forwarding(db, monkeypatch):
    from app.models import User
    user = User(username='alice', password_hash='unused', role='user', is_active=True)
    db.add(user)
    db.commit()
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    calls = []
    monkeypatch.setattr(auth, '_password_status', lambda *args: calls.append(args) or (False, False))
    try:
        client = TestClient(app)
        for i in range(10):
            assert client.post('/auth/login', json={'username': 'alice', 'password': 'bad'}).status_code == 401
        response = client.post('/auth/login', json={'username': 'alice', 'password': 'bad'}, headers={'X-Forwarded-For': '198.51.100.10'})
        assert response.status_code == 429
        assert len(calls) == 10
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize('payload', [{'username': [], 'password': 'secret-canary'}, {'username': 'a', 'password': {}}, {'username': 'a', 'password': 'x' * 16385}])
def test_malformed_login_rejected_without_echoing_credentials(payload):
    response = TestClient(app, raise_server_exceptions=False).post('/auth/login', json=payload)
    assert response.status_code == 400
    assert 'secret-canary' not in response.text


def test_existing_database_startup_requires_pepper(monkeypatch):
    from app.main import initialize_server
    monkeypatch.delenv('PASSWORD_PEPPER')
    with pytest.raises(SystemExit):
        initialize_server()


def test_validation_errors_do_not_reflect_passwords():
    from app.security import require_admin
    from app.models import User
    app.dependency_overrides[require_admin] = lambda: User(id=99, role='Root')
    try:
        response = TestClient(app).post('/settings/users', json={'username': 'bob', 'password': ['secret-canary']})
        assert response.status_code == 422
        assert 'secret-canary' not in response.text
    finally:
        app.dependency_overrides.clear()


def test_example_jwt_secret_is_rejected(monkeypatch):
    monkeypatch.setattr(auth, 'JWT_SECRET', 'CHANGE_ME_TO_A_LONG_RANDOM_STRING_AT_LEAST_32_CHARACTERS')
    with pytest.raises(RuntimeError):
        auth.validate_jwt_secret()


def test_transport_errors_are_sanitized_without_unhandled_tracebacks(monkeypatch):
    import httpx
    from app.security import get_current_user
    from app.rate_limit import check_user_rate_limit
    from app.models import User
    from app.routes.weather import check_openweather_limit
    original = httpx.AsyncClient
    def fail(req):
        raise httpx.ConnectError('secret-canary', request=req)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(fail), **kw))
    app.dependency_overrides[get_current_user] = lambda: User(id=1, role='user')
    app.dependency_overrides[check_user_rate_limit] = lambda: None
    app.dependency_overrides[check_openweather_limit] = lambda: None
    try:
        response = TestClient(app, raise_server_exceptions=False).get('/weather', params={'city': 'test'})
        assert response.status_code == 502
        assert 'secret-canary' not in response.text
    finally:
        app.dependency_overrides.clear()
