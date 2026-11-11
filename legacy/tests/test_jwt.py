import time
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import jwt
from app import auth
from app.models import User
from app.security import get_current_user
from app.routes.settings.users import update_user, disable_user, enable_user, UserUpdate


def test_tokens_require_claims_and_valid_subject():
    for payload in [{'sub': '1'}, {'sub': 'not-an-id', 'exp': time.time()+60}]:
        token = jwt.encode(payload, auth.JWT_SECRET, algorithm='HS256')
        with pytest.raises(HTTPException) as invalid:
            auth.decode_token(token)
        assert invalid.value.status_code == 401


def test_signing_secret_must_be_strong(monkeypatch):
    monkeypatch.setattr(auth, 'JWT_SECRET', 'weak')
    with pytest.raises(RuntimeError, match='JWT_SECRET'):
        auth.create_token(User(id=1, username='alice', role='user', password_hash='hash'))


def test_token_rejected_after_disable_and_reenable(db):
    user = User(username='alice', role='user', password_hash='hash', is_active=True)
    db.add(user)
    db.commit()
    token = auth.create_token(user)
    creds = HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)
    assert get_current_user(creds, db).id == user.id
    root = User(id=999, role='Root')
    disable_user(user.id, db, root)
    enable_user(user.id, db, root)
    with pytest.raises(HTTPException) as revoked:
        get_current_user(creds, db)
    assert revoked.value.status_code == 401


@pytest.mark.parametrize('change', ['password', 'role_roundtrip', 'delete'])
def test_tokens_revoked_after_account_changes(db, change):
    user = User(username='alice', role='user', password_hash='hash', is_active=True)
    db.add(user)
    db.commit()
    creds = HTTPAuthorizationCredentials(scheme='Bearer', credentials=auth.create_token(user))
    root = User(id=999, role='Root')
    if change == 'password':
        update_user(user.id, UserUpdate(password='new-example-password'), db, root)
    elif change == 'role_roundtrip':
        update_user(user.id, UserUpdate(role='admin'), db, root)
        update_user(user.id, UserUpdate(role='user'), db, root)
    else:
        db.delete(user)
        db.commit()
    with pytest.raises(HTTPException) as invalid:
        get_current_user(creds, db)
    assert invalid.value.status_code == 401
