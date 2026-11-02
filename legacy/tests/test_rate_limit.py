"""Regression tests for the actual DB-configured RateLimitStore interface."""
from app.rate_limit import RateLimitStore
from app.config import ROLE_DEFAULTS


def test_user_rate_limit():
    store = RateLimitStore()
    for remaining in (2, 1, 0):
        allowed, actual, reset = store.check_and_increment_user(1, 3)
        assert allowed and actual == remaining
    assert store.check_and_increment_user(1, 3) == (False, 0, reset)


def test_api_rate_limit():
    store = RateLimitStore()
    assert store.check_and_increment_api('nasa', 1)[:2] == (True, 0)
    assert store.check_and_increment_api('nasa', 1)[:2] == (False, 0)


def test_different_roles():
    assert ROLE_DEFAULTS['Root'] > ROLE_DEFAULTS['superAdmin'] > ROLE_DEFAULTS['admin'] > ROLE_DEFAULTS['user']


def test_cleanup():
    store = RateLimitStore()
    store.user_requests[1]['2000-01-01-00'] = 5
    store.api_requests['nasa']['2000-01-01-00'] = 5
    store._cleanup_expired()
    assert not store.user_requests and not store.api_requests


def test_multiple_users():
    store = RateLimitStore()
    assert store.check_and_increment_user(1, 2)[:2] == (True, 1)
    assert store.check_and_increment_user(2, 2)[:2] == (True, 1)
    assert store.check_and_increment_user(1, 2)[:2] == (True, 0)


def test_reset_timestamp_is_utc_even_on_non_utc_hosts(monkeypatch):
    import os
    import time
    old_tz = os.environ.get('TZ')
    monkeypatch.setenv('TZ', 'Europe/Zurich')
    time.tzset()
    try:
        now = time.time()
        reset = RateLimitStore().check_and_increment_user(1, 1)[2]
        assert 0 < reset - now <= 3600
    finally:
        if old_tz is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = old_tz
        time.tzset()
