"""
API Gateway client.

Handles JWT auth (auto-refresh at 55 min) and exposes every endpoint the
gateway provides: weather, geo, email, software/hardware heartbeats.

Usage:
    from gateway import GatewayClient

    gw = GatewayClient("https://api.novaroma-homelab.uk", "username", "password")
    print(gw.get_weather("Zurich"))
    gw.push_software_heartbeat("my-app", "ok", {"version": "1.0"})
"""

import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class GatewayClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    # ── auth ────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        """Return a cached token or log in for a fresh one."""
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token

        r = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=10,
        )
        r.raise_for_status()

        self._token = r.json()["access_token"]
        self._token_expiry = datetime.now() + timedelta(minutes=55)  # token lives 60 min
        return self._token

    # ── generic requests ────────────────────────────────────────────

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        token = self._get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        r = requests.request(
            method,
            f"{self.base_url}{endpoint}",
            headers=headers,
            **kwargs,
        )
        r.raise_for_status()
        return r.json()

    def get(self, endpoint: str, **kwargs) -> Any:
        return self._request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> Any:
        return self._request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs) -> Any:
        return self._request("PUT", endpoint, **kwargs)

    # ── weather ─────────────────────────────────────────────────────

    def get_weather(self, city: str, units: str = "metric") -> Dict[str, Any]:
        return self.get("/weather", params={"city": city, "units": units})

    def get_hourly_forecast(self, lat: float, lon: float, units: str = "metric") -> Dict[str, Any]:
        return self.get("/weather/forecast/hourly", params={"lat": lat, "lon": lon, "units": units})

    def get_daily_forecast(self, lat: float, lon: float, days: int = 7, units: str = "metric") -> Dict[str, Any]:
        return self.get("/weather/forecast/daily", params={"lat": lat, "lon": lon, "cnt": days, "units": units})

    # ── geo ─────────────────────────────────────────────────────────

    def geocode(self, city: str) -> Dict[str, Any]:
        return self.get("/geo/geocode", params={"text": city})

    def get_location_from_ip(self, ip: Optional[str] = None) -> Dict[str, Any]:
        params = {"ip": ip} if ip else {}
        return self.get("/geo/ip", params=params)

    # ── telephone ───────────────────────────────────────────────────

    def telephone_search(self, was: str, wo: str) -> Dict[str, Any]:
        return self.get("/telephone/search", params={"was": was, "wo": wo})

    # ── nasa ────────────────────────────────────────────────────────

    def nasa_apod(self, date: Optional[str] = None, hd: bool = False) -> Dict[str, Any]:
        params: Dict[str, Any] = {"hd": hd}
        if date:
            params["date"] = date
        return self.get("/nasa/apod", params=params)

    def nasa_epic(self, collection: str = "natural") -> Dict[str, Any]:
        return self.get(f"/nasa/epic/{collection}")

    def nasa_epic_available(self, collection: str = "natural") -> Dict[str, Any]:
        return self.get(f"/nasa/epic/{collection}/available")

    # ── library ─────────────────────────────────────────────────────

    def library_search(self, q: str, limit: int = 10) -> Dict[str, Any]:
        return self.get("/library/search", params={"q": q, "limit": limit})

    def library_books(self, bibkeys: str) -> Dict[str, Any]:
        return self.get("/library/books", params={"bibkeys": bibkeys})

    def library_authors(self, author_id: str) -> Dict[str, Any]:
        return self.get(f"/library/authors/{author_id}")

    def library_subjects(self, subject: str, limit: int = 20) -> Dict[str, Any]:
        return self.get(f"/library/subjects/{subject}", params={"limit": limit})

    # ── email ───────────────────────────────────────────────────────

    def send_email(self, to: list, subject: str, html: str, from_email: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "html": html,
        }
        if from_email:
            payload["from_email"] = from_email
        return self.post("/email/send", json=payload)

    def send_email_simple(self, to_users: list, subject: str, html: str, from_name: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "to_users": to_users if isinstance(to_users, list) else [to_users],
            "subject": subject,
            "html": html,
        }
        if from_name:
            payload["from_name"] = from_name
        return self.post("/email/send-simple", json=payload)

    # ── software health ─────────────────────────────────────────────

    def list_software(self) -> list:
        return self.get("/software")

    def get_software(self, name: str) -> Dict[str, Any]:
        return self.get(f"/software/{name}")

    def push_software_heartbeat(self, name: str, health: str, details: Optional[Dict] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"health": health}
        if details is not None:
            payload["details"] = details
        return self.post(f"/software/{name}/heartbeat", json=payload)

    # ── hardware health ─────────────────────────────────────────────

    def list_hardware(self) -> list:
        return self.get("/hardware")

    def get_hardware(self, name: str) -> Dict[str, Any]:
        return self.get(f"/hardware/{name}")

    def push_hardware_heartbeat(self, name: str, health: str, config: Optional[Dict] = None, details: Optional[Dict] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"health": health}
        if config is not None:
            payload["config"] = config
        if details is not None:
            payload["details"] = details
        return self.post(f"/hardware/{name}/heartbeat", json=payload)

    # ── rate limits ─────────────────────────────────────────────────

    def get_my_rate_limits(self) -> Dict[str, Any]:
        return self.get("/rate-limits/me")

    def get_api_rate_limits(self) -> Dict[str, Any]:
        return self.get("/rate-limits/apis")

    # ── settings: users (admin+) ────────────────────────────────────
    # Requires at least the admin role.  Only Root can delete users;
    # other mutations are blocked server-side for lower roles.

    def list_users(self) -> list:
        """GET /settings/users → [{id, username, role, is_active}, …]"""
        return self.get("/settings/users")

    def create_user(self, username: str, password: str, role: str = "user") -> Dict[str, Any]:
        """POST /settings/users — register a new user."""
        return self.post("/settings/users", json={"username": username, "password": password, "role": role})

    def enable_user(self, user_id: int) -> Dict[str, Any]:
        """POST /settings/users/{id}/enable"""
        return self.post(f"/settings/users/{user_id}/enable")

    def disable_user(self, user_id: int) -> Dict[str, Any]:
        """POST /settings/users/{id}/disable"""
        return self.post(f"/settings/users/{user_id}/disable")

    # ── settings: APIs (superAdmin+) ─────────────────────────────────

    def list_apis(self) -> list:
        """GET /settings/apis → [{api_name, is_active, max_calls_per_hour}, …]"""
        return self.get("/settings/apis")

    def set_api_active(self, api_name: str, active: bool) -> Dict[str, Any]:
        """PUT /settings/apis/{name} — toggle an API on/off."""
        return self.put(f"/settings/apis/{api_name}", json={"is_active": active})

    # ── settings: roles (superAdmin+ / Root) ────────────────────────
    # Toggling roles is superAdmin+; changing the hourly limit is Root only.

    def list_roles(self) -> list:
        """GET /settings/roles → [{role_name, is_active, max_calls_per_hour}, …]"""
        return self.get("/settings/roles")

    def set_role_active(self, role_name: str, active: bool) -> Dict[str, Any]:
        """PUT /settings/roles/{name} — toggle a role on/off."""
        return self.put(f"/settings/roles/{role_name}", json={"is_active": active})

    def set_role_limit(self, role_name: str, max_calls_per_hour: int) -> Dict[str, Any]:
        """PUT /settings/roles/{name} — change hourly request limit (Root only)."""
        return self.put(f"/settings/roles/{role_name}", json={"max_calls_per_hour": max_calls_per_hour})

    # ── settings: software (admin+) ──────────────────────────────────

    def list_software_settings(self) -> list:
        """GET /settings/software → [{name, is_active}, …]"""
        return self.get("/settings/software")

    def register_software(self, name: str) -> Dict[str, Any]:
        """POST /settings/software — register a new software entry."""
        return self.post("/settings/software", json={"name": name})

    # ── settings: hardware (admin+ / superAdmin+) ───────────────────
    # Registering and listing is admin+.  Updating config is superAdmin+.

    def list_hardware_settings(self) -> list:
        """GET /settings/hardware → [{name, config, is_active}, …]"""
        return self.get("/settings/hardware")

    def get_hardware_config(self, name: str) -> tuple:
        """Extract (config, is_active) for one device from /settings/hardware.

        Returns (None, True) when the device is not registered so that an
        absent entry never accidentally triggers a kill.
        """
        for hw in self.list_hardware_settings():
            if hw.get("name") == name:
                return hw.get("config"), hw.get("is_active", True)
        return None, True

    def register_hardware(self, name: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """POST /settings/hardware — register a new device (admin+)."""
        payload: Dict[str, Any] = {"name": name}
        if config is not None:
            payload["config"] = config
        return self.post("/settings/hardware", json=payload)

    def update_hardware_config(self, name: str, config: Dict) -> Dict[str, Any]:
        """PUT /settings/hardware/{name} — push new config to a device (superAdmin+)."""
        return self.put(f"/settings/hardware/{name}", json={"config": config})
