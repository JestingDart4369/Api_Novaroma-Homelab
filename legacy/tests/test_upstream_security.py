import asyncio
import httpx
import pytest
from fastapi import HTTPException
from app.routes import library, pushcut, email
from app.models import User


def test_archive_does_not_follow_redirect_to_private_network(monkeypatch):
    requests = []
    original = httpx.AsyncClient
    def upstream(req):
        requests.append(str(req.url))
        if req.url.host == 's3.us.archive.org':
            return httpx.Response(302, headers={'location': 'http://127.0.0.1/metadata'})
        return httpx.Response(200, text='private data')
    monkeypatch.setattr(library.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(upstream), **kw))
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(library.get_archive_file('bucket', 'file.txt'))
    assert rejected.value.status_code == 502
    assert len(requests) == 1


def test_pushcut_does_not_leak_upstream_error_body(monkeypatch):
    original = httpx.AsyncClient
    monkeypatch.setattr(pushcut.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(lambda _: httpx.Response(403, json={'api-key': 'secret-canary'})), **kw))
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(pushcut._pushcut_request('GET', '/devices'))
    assert 'secret-canary' not in str(rejected.value.detail)


@pytest.mark.parametrize('simple', [False, True])
def test_email_does_not_leak_sdk_error(monkeypatch, simple):
    def fail(*args, **kwargs):
        raise RuntimeError('secret-canary')
    monkeypatch.setattr(email.resend.Emails, 'send', fail)
    body = email.SimpleEmailRequest(to_users=['alice'], subject='test', html='test') if simple else email.EmailRequest(to=['alice@example.com'], subject='test', html='test')
    with pytest.raises(HTTPException) as rejected:
        asyncio.run((email.send_simple_email if simple else email.send_email)(body, User(username='alice')))
    assert 'secret-canary' not in str(rejected.value.detail)


def test_notifications_never_email_or_print_exception_secrets(monkeypatch, capsys):
    from app import notifications
    sent = []
    monkeypatch.setenv('ADMIN_EMAIL', 'admin@example.com')
    monkeypatch.setattr(notifications.resend.Emails, 'send', lambda value: sent.append(value))
    notifications.notify_critical_error(RuntimeError('secret-canary'))
    assert 'secret-canary' not in str(sent)
    assert 'secret-canary' not in capsys.readouterr().out


def test_archive_paths_cannot_override_query_or_escape_bucket(monkeypatch):
    seen = []
    original = httpx.AsyncClient
    def upstream(req):
        seen.append(req.url)
        return httpx.Response(200, content=b'ok')
    monkeypatch.setattr(library.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(upstream), **kw))
    asyncio.run(library.get_archive_file('bucket', 'chapter?x=1#notes.txt'))
    assert not seen[0].query
    assert not seen[0].fragment
    assert '%3F' in str(seen[0])
    with pytest.raises(HTTPException) as invalid:
        asyncio.run(library.get_archive_file('..', 'other/file'))
    assert invalid.value.status_code == 400
