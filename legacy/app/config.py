# ============================================================
# API & ROLE CONFIG LOADER
# ============================================================
# Reads all settings from .env file.
#
# To add a new API:
#   1. Add these lines to .env:
#        MYAPI_KEY=your_key_here
#        MYAPI_ENABLED=true
#        MYAPI_MAX_CALLS=1000
#   2. Add one line to API_REGISTRY below:
#        "myapi": "MYAPI",
#   3. Create the route file following the blueprint
# ============================================================
import os

# ============================================================
# API REGISTRY
# ============================================================
# Maps internal api_name (used in api_config table + rate limiter)
# -> env var prefix (used to find KEY, ENABLED, MAX_CALLS in .env)
# ============================================================
API_REGISTRY = {
    "openweather": "OPENWEATHER",
    "geoapify":    "GEOAPIFY",
    "ipregistry":  "IPREGISTRY",
    "resend":      "RESEND",
    "telephone":   "TELEPHONE",
    "nasa":        "NASA",
    "openlibrary": "OPENLIBRARY",
    "pushcut":     "PUSHCUT",
    "grade":       "GRADE",
}

# ============================================================
# ROLE LIMIT ENV VAR NAMES
# ============================================================
# Maps role_name -> env var that holds max calls per hour
# ============================================================
ROLE_ENV_VARS = {
    "user":       "ROLE_USER_MAX_CALLS",
    "admin":      "ROLE_ADMIN_MAX_CALLS",
    "superAdmin": "ROLE_SUPERADMIN_MAX_CALLS",
    "Root":       "ROLE_ROOT_MAX_CALLS",
}

# Fallback values if env var is missing
ROLE_DEFAULTS = {
    "user":       1000,
    "admin":      2000,
    "superAdmin": 5000,
    "Root":       10000,
}

# ============================================================
# LOADERS
# ============================================================

def get_key(api_name: str) -> str:
    """Get the API key for a given api_name. Raises if missing."""
    prefix = API_REGISTRY.get(api_name)
    if not prefix:
        raise ValueError(f"API '{api_name}' not in API_REGISTRY")
    key = os.environ.get(f"{prefix}_KEY")
    if not key:
        raise ValueError(f"Missing env var: {prefix}_KEY")
    return key


def load_api_config(api_name: str) -> dict:
    """Load a single API's full config from .env."""
    prefix = API_REGISTRY.get(api_name)
    if not prefix:
        raise ValueError(f"API '{api_name}' not in API_REGISTRY")
    return {
        "name":              api_name,
        "key":               os.environ.get(f"{prefix}_KEY"),
        "enabled":           os.environ.get(f"{prefix}_ENABLED", "true").lower() == "true",
        "max_calls_per_hour": int(os.environ.get(f"{prefix}_MAX_CALLS", "1000")),
    }


def load_all_api_configs() -> list:
    """Load every API's config from .env. Used by the seeder."""
    return [load_api_config(name) for name in API_REGISTRY]


def load_all_role_configs() -> list:
    """Load every role's config from .env. Used by the seeder."""
    return [
        {
            "role_name":          role,
            "max_calls_per_hour": int(os.environ.get(env_var, ROLE_DEFAULTS[role])),
        }
        for role, env_var in ROLE_ENV_VARS.items()
    ]
