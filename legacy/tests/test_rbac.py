import pytest
from fastapi import HTTPException
from app.models import User
from app.routes.settings.users import create_user, update_user, disable_user, enable_user, UserCreate, UserUpdate
from pydantic import ValidationError


@pytest.mark.parametrize('password', ['', 'short', 'x' * 16385])
def test_new_account_and_reset_password_policy(password):
    with pytest.raises(ValidationError):
        UserCreate(username='alice', password=password)
    with pytest.raises(ValidationError):
        UserUpdate(password=password)


@pytest.mark.parametrize('actor,role', [('admin','admin'), ('admin','Root'), ('admin','superAdmin'), ('superAdmin','superAdmin'), ('superAdmin','Root')])
def test_cannot_create_peer_or_higher_privilege(db, actor, role):
    admin = User(id=100, username='actor', role=actor)
    with pytest.raises(HTTPException) as denied:
        create_user(UserCreate(username='attacker', password='example-password', role=role), db, admin)
    assert denied.value.status_code == 403
    assert db.query(User).count() == 0

@pytest.mark.parametrize('action', ['reset', 'role', 'disable', 'enable'])
def test_cannot_modify_peer_or_higher_account(db, action):
    target = User(username='root', password_hash='untouched', role='Root', is_active=True)
    db.add(target)
    db.commit()
    actor = User(id=999, username='super', role='superAdmin')
    with pytest.raises(HTTPException) as denied:
        if action == 'reset':
            update_user(target.id, UserUpdate(password='attacker-password'), db, actor)
        elif action == 'role':
            update_user(target.id, UserUpdate(role='user'), db, actor)
        elif action == 'disable':
            disable_user(target.id, db, actor)
        else:
            enable_user(target.id, db, actor)
    assert denied.value.status_code == 403


def test_superadmin_cannot_promote_lower_user_to_root(db):
    target = User(username='target', password_hash='untouched', role='user', is_active=True)
    db.add(target)
    db.commit()
    with pytest.raises(HTTPException) as denied:
        update_user(target.id, UserUpdate(role='Root'), db, User(id=999, role='superAdmin'))
    assert denied.value.status_code == 403
