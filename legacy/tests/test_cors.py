import pytest
from fastapi.testclient import TestClient

import app.notifications
app.notifications.notify_startup_success = lambda: None
app.notifications.notify_startup_error = lambda error: None
from app.cors import DEFAULT_ORIGINS, parse_origins
from app.main import app

SITE = 'https://novaroma-homelab.uk'


def test_allowed_origin_gets_cors_header_on_health():
    response = TestClient(app).get('/health', headers={'Origin': SITE})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == SITE
    assert 'access-control-allow-credentials' not in response.headers


def test_svenja_subdomain_is_allowed():
    origin = 'https://svenja.novaroma-homelab.uk'
    response = TestClient(app).get('/health', headers={'Origin': origin})
    assert response.headers['access-control-allow-origin'] == origin


@pytest.mark.parametrize('origin', ['https://evil.example', 'http://novaroma-homelab.uk',
                                    'https://novaroma-homelab.uk.evil.example', 'null'])
def test_other_origins_get_no_cors_header(origin):
    response = TestClient(app).get('/health', headers={'Origin': origin})
    assert 'access-control-allow-origin' not in response.headers


def test_preflight_for_login_is_answered_for_allowed_origin_only():
    headers = {'Origin': SITE, 'Access-Control-Request-Method': 'POST',
               'Access-Control-Request-Headers': 'authorization,content-type'}
    ok = TestClient(app).options('/auth/login', headers=headers)
    assert ok.status_code == 200
    assert ok.headers['access-control-allow-origin'] == SITE
    assert 'POST' in ok.headers['access-control-allow-methods']
    bad = TestClient(app).options('/auth/login', headers={**headers, 'Origin': 'https://evil.example'})
    assert bad.status_code == 400
    assert 'access-control-allow-origin' not in bad.headers


def test_destructive_methods_are_not_allowed_cross_origin():
    headers = {'Origin': SITE, 'Access-Control-Request-Method': 'DELETE'}
    response = TestClient(app).options('/settings/users/1', headers=headers)
    assert response.status_code == 400


def test_defaults_and_parsing():
    assert parse_origins(DEFAULT_ORIGINS) == [SITE, 'https://svenja.novaroma-homelab.uk']
    assert parse_origins(' https://a.example/ , https://a.example,') == ['https://a.example']
    assert parse_origins('') == []


@pytest.mark.parametrize('bad', ['*', 'https://*.example.com', 'example.com', 'https://a.example/path',
                                 'ftp://a.example', 'https://a.example?x=1'])
def test_wildcards_and_non_origins_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_origins(bad)
