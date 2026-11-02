import hashlib
import pytest
from fastapi import HTTPException
from app import auth
from app.models import User


def test_new_passwords_are_salted_argon2id_and_require_pepper(monkeypatch):
    a = auth.hash_password('correct horse')
    b = auth.hash_password('correct horse')
    assert a.startswith('v1$argon2id$')
    assert a != b
    assert auth.verify_password('correct horse', a)
    assert not auth.verify_password('wrong', a)
    monkeypatch.setenv('PASSWORD_PEPPER', 'different-test-pepper-' * 3)
    assert not auth.verify_password('correct horse', a)
    monkeypatch.delenv('PASSWORD_PEPPER')
    with pytest.raises(RuntimeError, match='pepper'):
        auth.hash_password('correct horse')


@pytest.mark.parametrize('password', ['short legacy', 'ä' * 80])
def test_legacy_passwords_migrate_on_success_only(db, password):
    legacy_input = hashlib.sha256(password.encode()).hexdigest() if len(password.encode()) > 72 else password
    old = auth.bcrypt.hashpw(legacy_input.encode(), auth.bcrypt.gensalt()).decode()
    user = User(username='legacy', password_hash=old, role='user', is_active=True)
    db.add(user)
    db.commit()
    with pytest.raises(HTTPException):
        auth.verify_login(db, 'legacy', 'wrong')
    assert user.password_hash == old
    assert auth.verify_login(db, 'legacy', password).id == user.id
    assert user.password_hash.startswith('v1$argon2id$')
    assert auth.verify_password(password, user.password_hash)
    if len(password.encode()) > 72:
        # A bcrypt truncated-prefix password must not be accepted.
        assert not auth.verify_password(password[:36] + 'x', old)


def test_pepper_rotation_rehashes_with_current_key(db, monkeypatch):
    old_pepper = auth.get_pepper().decode()
    old_hash = auth.hash_password('rotation-password')
    db.add(User(username='rotating', password_hash=old_hash, role='user', is_active=True))
    db.commit()
    monkeypatch.setenv('PASSWORD_PEPPER', 'new-test-pepper-for-rotation-' * 3)
    monkeypatch.setenv('PASSWORD_PREVIOUS_PEPPER', old_pepper)
    user = auth.verify_login(db, 'rotating', 'rotation-password')
    assert user.password_hash != old_hash
    monkeypatch.delenv('PASSWORD_PREVIOUS_PEPPER')
    assert auth.verify_password('rotation-password', user.password_hash)
    assert not auth.verify_password('rotation-password', old_hash)


def test_pepper_secret_file_is_supported_and_missing_pepper_fails_closed(tmp_path, monkeypatch):
    pepper_file = tmp_path / 'pepper'
    pepper_file.write_text('offline-secret-file-pepper-' * 3 + '\n')
    monkeypatch.delenv('PASSWORD_PEPPER')
    monkeypatch.setenv('PASSWORD_PEPPER_FILE', str(pepper_file))
    stored = auth.hash_password('secret-file-password')
    assert auth.verify_password('secret-file-password', stored)
    monkeypatch.delenv('PASSWORD_PEPPER_FILE')
    with pytest.raises(RuntimeError, match='pepper'):
        auth.verify_password('secret-file-password', stored)


def test_sql_injection_payload_is_a_literal_username(db):
    db.add(User(username='alice', password_hash='not-a-hash', role='Root', is_active=True))
    db.commit()
    with pytest.raises(HTTPException) as invalid:
        auth.verify_login(db, "' OR 1=1 --", 'password')
    assert invalid.value.status_code == 401
    assert db.query(User).one().username == 'alice'


def test_migration_cannot_authenticate_against_a_concurrent_password_reset(db):
    from sqlalchemy import event, update
    user = User(username='racing', password_hash=auth.bcrypt.hashpw(b'legacy-password', auth.bcrypt.gensalt()).decode(), role='user', is_active=True)
    db.add(user)
    db.commit()
    def concurrent_reset(_):
        with db.get_bind().begin() as connection:
            connection.execute(update(User).where(User.id == user.id).values(password_hash='concurrent-admin-reset'))
    event.listen(db, 'after_commit', concurrent_reset, once=True)
    with pytest.raises(HTTPException) as invalid:
        auth.verify_login(db, 'racing', 'legacy-password')
    assert invalid.value.status_code == 401
