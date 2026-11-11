import os
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Never load a developer/production database or provider credentials.
_TEST_DIR = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
os.environ['DB_URL'] = 'sqlite:///' + _TEST_DIR.name + '/test.db'
os.environ['JWT_SECRET'] = 'test-only-signing-key-' * 3
os.environ['PASSWORD_PEPPER'] = 'test-only-password-pepper-' * 3
for prefix in ['OPENWEATHER', 'GEOAPIFY', 'IPREGISTRY', 'RESEND', 'TELEPHONE', 'NASA', 'OPENLIBRARY', 'PUSHCUT', 'GRADE']:
    os.environ[prefix + '_KEY'] = 'offline-test-key'
for name in ['ADMIN_EMAIL', 'BOOTSTRAP_ADMIN_USERNAME', 'BOOTSTRAP_ADMIN_PASSWORD', 'RESEND_API_KEY']:
    os.environ.pop(name, None)

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from app.db import Base

@pytest.fixture
def db(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'db.sqlite'))
    @event.listens_for(engine, 'connect')
    def test_only_fast_io(connection, _):
        # Disposable tests only: avoid host fsync stalls, keep SQLite locking real.
        connection.execute('PRAGMA synchronous=OFF')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
