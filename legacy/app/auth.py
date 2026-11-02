import os
import time
import hashlib
import hmac
import uuid
from pathlib import Path
import jwt
from jwt import InvalidTokenError
import bcrypt
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException
from sqlalchemy.orm import Session, object_session
from app.models import User, LoginAttempt, TokenState
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy import delete, case



def check_login_budget(engine, username: str, request, now=None):
    """Atomic SQLite budget, shared across workers/restarts; never use forwarded headers."""
    now = int(time.time() if now is None else now)
    window = now // 900
    source = request.client.host if request.client else 'unknown'
    blocked = False
    with engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA busy_timeout=60000')
        conn.execute(delete(LoginAttempt).where(LoginAttempt.window < window - 1))
        for scope, identity, limit in [('source', source, 50), ('account', username, 10)]:
            key = scope + ':' + hashlib.sha256(identity.encode()).hexdigest()
            stmt = insert(LoginAttempt).values(key=key, window=window, count=1)
            stmt = stmt.on_conflict_do_update(
                index_elements=['key'],
                set_={'window': window, 'count': case((LoginAttempt.window != window, 1), else_=LoginAttempt.count + 1)},
                where=(LoginAttempt.window != window) | (LoginAttempt.count < limit),
            ).returning(LoginAttempt.count)
            if conn.execute(stmt).first() is None:
                blocked = True
                break
    if blocked:
        raise HTTPException(429, 'Too many login attempts', headers={'Retry-After': str((window + 1) * 900 - now)})

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
JWT_ISSUER = 'novaroma-api'
JWT_AUDIENCE = 'novaroma-api-clients'


def validate_jwt_secret():
    if len(JWT_SECRET.encode()) < 32 or JWT_SECRET.lower().startswith(('change', 'your-secret', 'your_secret')):
        raise RuntimeError('JWT_SECRET must be an independent random secret of at least 32 bytes')


def invalidate_tokens(db, user):
    stmt = insert(TokenState).values(user_id=user.id, nonce=uuid.uuid4().hex)
    db.execute(stmt.on_conflict_do_update(index_elements=['user_id'], set_={'nonce': stmt.excluded.nonce}))


def credential_version(db, user):
    state = db.get(TokenState, user.id) if db is not None else None
    message = '\0'.join([user.password_hash, user.role, state.nonce if state else '0'])
    return hmac.new(JWT_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, type=Type.ID)


def _read_pepper(name: str, required=False):
    value = os.environ.get(name)
    filename = os.environ.get(name + '_FILE')
    if value and filename:
        raise RuntimeError("Configure only one password pepper source")
    if filename:
        try:
            value = Path(filename).read_text().strip()
        except OSError:
            raise RuntimeError('Cannot read password pepper file') from None
    if not value and not required:
        return None
    if not value or len(value.encode()) < 32:
        raise RuntimeError("A password pepper of at least 32 bytes is required")
    return value.encode()


def get_pepper() -> bytes:
    pepper = _read_pepper('PASSWORD_PEPPER', required=True)
    assert pepper is not None  # required=True already rejects a missing secret.
    return pepper


def _peppered(password: str) -> str:
    return hmac.new(get_pepper(), password.encode('utf-8'), hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    return 'v1' + password_hasher.hash(_peppered(password))


def verify_password(password: str, password_hash: str) -> bool:
    return _password_status(password, password_hash)[0]


def _password_status(password: str, password_hash: str):
    # Require the current pepper even for legacy verification.
    current = get_pepper()
    previous = _read_pepper('PASSWORD_PREVIOUS_PEPPER')
    try:
        if password_hash.startswith('v1$argon2id$'):
            for index, pepper in enumerate([current, previous] if previous else [current]):
                candidate = hmac.new(pepper, password.encode('utf-8'), hashlib.sha256).hexdigest()
                try:
                    if password_hasher.verify(password_hash[2:], candidate):
                        return True, bool(index) or password_hasher.check_needs_rehash(password_hash[2:])
                except VerificationError:
                    continue
            return False, False
        if password_hash.startswith(('$2a$', '$2b$', '$2y$')):
            if len(password.encode('utf-8')) > 72:
                password = hashlib.sha256(password.encode('utf-8')).hexdigest()
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('ascii')), True
        return False, False
    except (VerificationError, InvalidHashError, ValueError, TypeError):
        return False, False

#Create the bearer token payload
def create_token(user: User) -> str:
    validate_jwt_secret()
    now = int(time.time())
    payload = {
        "sub": str(user.id),          # stable identity
        "username": user.username,    # convenience
        "role": user.role,
        "iat": now,
        "exp": now + 3600,            # 1 hour
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "jti": uuid.uuid4().hex,
        "cv": credential_version(object_session(user), user),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

#decode the token to see if its right
def decode_token(token: str) -> dict:
    validate_jwt_secret()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG], issuer=JWT_ISSUER, audience=JWT_AUDIENCE,
                             options={'require': ['exp', 'iat', 'sub', 'jti', 'iss', 'aud', 'cv']})
        now = int(time.time())
        if (not isinstance(payload.get('sub'), str) or not payload['sub'].isascii() or not payload['sub'].isdigit()
                or not 0 < int(payload['sub']) <= 9223372036854775807
                or type(payload.get('iat')) is not int or type(payload.get('exp')) is not int
                or payload['iat'] > now or payload['exp'] <= payload['iat'] or payload['exp'] - payload['iat'] > 3600
                or payload.get('iss') != JWT_ISSUER or payload.get('aud') != JWT_AUDIENCE
                or not isinstance(payload.get('cv'), str) or len(payload['cv']) != 64):
            raise ValueError('Invalid claims')
        return payload
    except (InvalidTokenError, ValueError, TypeError, OverflowError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

#see if the user exist
def verify_login(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Bad credentials")
    verified, needs_rehash = _password_status(password, user.password_hash)
    if not verified:
        raise HTTPException(status_code=401, detail="Bad credentials")
    if needs_rehash:
        old_hash = user.password_hash
        new_hash = hash_password(password)
        # Compare-and-swap avoids overwriting a concurrent administrative reset.
        changed = db.query(User).filter(User.id == user.id, User.password_hash == old_hash, User.is_active.is_(True)).update({User.password_hash: new_hash}, synchronize_session=False)
        db.commit()
        db.refresh(user)
        if not changed or not user.is_active or user.password_hash != new_hash:
            raise HTTPException(status_code=401, detail="Bad credentials")
    return user