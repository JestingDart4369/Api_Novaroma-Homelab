from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app import auth


def request(host='192.0.2.1', forwarded='198.51.100.2'):
    return Request({'type': 'http', 'client': (host, 1234), 'headers': [(b'x-forwarded-for', forwarded.encode())]})


def test_login_budget_is_persistent_atomic_and_source_and_account_scoped(db):
    assert hasattr(auth, 'check_login_budget'), 'login must be limited before hashing'
    engine = db.get_bind()
    def attempt(i):
        try:
            auth.check_login_budget(engine, 'alice', request(f'192.0.2.{i}'), now=100)
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            assert int(exc.headers['Retry-After']) > 0
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(30))) == 10
    auth.check_login_budget(engine, 'bob', request('203.0.113.1'), now=100)
    for i in range(49):
        auth.check_login_budget(engine, f'other{i}', request('203.0.113.2', str(i)), now=100)
    auth.check_login_budget(engine, 'last', request('203.0.113.2'), now=100)
    with pytest.raises(HTTPException) as blocked:
        auth.check_login_budget(engine, 'fresh', request('203.0.113.2', 'spoof'), now=100)
    assert blocked.value.status_code == 429
    auth.check_login_budget(engine, 'alice', request(), now=1001)
