import json
from pathlib import Path


def test_uvicorn_cannot_rewrite_peer_from_forwarded_headers():
    dockerfile = (Path(__file__).resolve().parents[1] / 'Dockerfile').read_text()
    command = json.loads(next(line[4:] for line in dockerfile.splitlines() if line.startswith('CMD ')))
    assert '--no-proxy-headers' in command
    assert '--no-access-log' in command  # Grade legacy query strings contain credentials.
