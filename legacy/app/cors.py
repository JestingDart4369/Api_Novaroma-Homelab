"""Browser CORS policy: an explicit allowlist of website origins, never a wildcard."""
import os
from urllib.parse import urlsplit

# The static site and the Svenja subdomain call this API from the browser.
DEFAULT_ORIGINS = "https://novaroma-homelab.uk,https://svenja.novaroma-homelab.uk"


def parse_origins(raw: str) -> list[str]:
    """Parse a comma-separated origin list; reject anything that is not a plain origin."""
    origins = []
    for item in raw.split(","):
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        parts = urlsplit(origin)
        if (origin == "*" or parts.scheme not in ("http", "https") or not parts.netloc
                or parts.path or parts.query or parts.fragment or "*" in origin):
            raise ValueError(f"Invalid CORS_ALLOWED_ORIGINS entry: {item.strip()!r} "
                             "(use exact origins like https://example.com, no wildcards or paths)")
        if origin not in origins:
            origins.append(origin)
    return origins


def allowed_origins() -> list[str]:
    """Origins from CORS_ALLOWED_ORIGINS; an empty value disables CORS entirely."""
    return parse_origins(os.environ.get("CORS_ALLOWED_ORIGINS", DEFAULT_ORIGINS))
