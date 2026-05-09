# ============================================================
# IMPORTS
# ============================================================
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Optional
from app.security import get_current_user
from app.models import User
from app.config import get_key
from app.rate_limit import check_user_rate_limit, APIRateLimiter

# ============================================================
# ROUTER SETUP & CONFIG
# ============================================================
router = APIRouter(prefix="/pushcut", tags=["pushcut"])
API_KEY = get_key("pushcut")
BASE_URL = "https://api.pushcut.io/v1"

check_pushcut_limit = APIRateLimiter("pushcut")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET  /pushcut/devices                           - List active devices
# GET  /pushcut/notifications                     - List all defined notifications
# POST /pushcut/notifications/{notificationName}  - Send smart notification
# POST /pushcut/execute                           - Execute shortcut or HomeKit scene
# GET  /pushcut/subscriptions                     - List webhook subscriptions
# POST /pushcut/subscriptions                     - Register webhook
# DELETE /pushcut/subscriptions/{subscriptionId}  - Remove webhook subscription
#
# Auth: Required (JWT Bearer token)
#
# Rate Limits:
#   - User limit:  from role_limits table
#   - API limit:   from api_config table ("pushcut")
#
# Response:
#   200 - Success with JSON response
#   202 - Accepted (for scheduled requests)
#   204 - Success (for deletions)
#   400 - Invalid parameters
#   401 - Not authenticated / inactive user
#   429 - Rate limit exceeded
#   502 - Upstream API failed
#   503 - API disabled in config
# ============================================================

# ============================================================
# HELPER FUNCTION
# ============================================================

async def _pushcut_request(method: str, path: str, params: dict = None, json: dict = None):
    """
    Make authenticated request to Pushcut API.

    Args:
        method: HTTP method (GET, POST, DELETE)
        path: API path (e.g., "/devices")
        params: Query parameters
        json: Request body (for POST)

    Returns:
        Tuple of (status_code, response_data)
    """
    url = f"{BASE_URL}{path}"
    headers = {"API-Key": API_KEY}

    async with httpx.AsyncClient(timeout=15) as client:
        if method == "GET":
            r = await client.get(url, headers=headers, params=params)
        elif method == "POST":
            r = await client.post(url, headers=headers, params=params, json=json)
        elif method == "DELETE":
            r = await client.delete(url, headers=headers, params=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    # Handle different success codes
    if r.status_code in (200, 202, 204):
        # 204 No Content returns empty body
        return r.status_code, r.json() if r.status_code != 204 else {"success": True}

    # Handle errors
    try:
        error_detail = r.json()
    except:
        error_detail = {"error": r.text}

    raise HTTPException(
        status_code=502,
        detail=f"Pushcut API failed ({r.status_code}): {error_detail}"
    )

# ============================================================
# ENDPOINTS
# ============================================================

# --- List Active Devices ---
@router.get("/devices")
async def list_devices(
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_pushcut_limit),
):
    """
    List all active Pushcut devices registered to your account.

    Returns list of device objects with their IDs and names.
    """
    status, data = await _pushcut_request("GET", "/devices")
    return data


# --- List All Notifications ---
@router.get("/notifications")
async def list_notifications(
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_pushcut_limit),
):
    """
    List all notification definitions configured in your Pushcut account.

    Returns list of notification names and their configurations.
    """
    status, data = await _pushcut_request("GET", "/notifications")
    return data


# --- Send Smart Notification ---
@router.post("/notifications/{notificationName}")
async def send_notification(
    notificationName: str,
    text: Optional[str] = Query(None, description="Notification body text"),
    title: Optional[str] = Query(None, description="Notification title"),
    image: Optional[str] = Query(None, description="Image URL or base64 data"),
    input: Optional[str] = Query(None, description="Input value for notification action"),
    devices: Optional[str] = Query(None, description="Comma-separated device IDs (omit for all devices)"),
    isUpdate: Optional[bool] = Query(None, description="Update existing notification instead of new"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_pushcut_limit),
    body: Optional[dict] = Body(None, description="Full notification payload (overrides query params)"),
):
    """
    Send a smart notification to your Pushcut devices.

    Can provide params via query string OR via JSON body.
    JSON body takes precedence if both are provided.

    Example JSON body:
    {
        "text": "Hello World",
        "title": "My Notification",
        "image": "https://example.com/image.png",
        "input": "default value",
        "devices": ["device-id-1", "device-id-2"],
        "isUpdate": false
    }
    """
    # Build params from query string
    params = {}
    if text:
        params["text"] = text
    if title:
        params["title"] = title
    if image:
        params["image"] = image
    if input:
        params["input"] = input
    if devices:
        params["devices"] = devices
    if isUpdate is not None:
        params["isUpdate"] = str(isUpdate).lower()

    # Use JSON body if provided (overrides query params)
    json_data = body if body else None

    status, data = await _pushcut_request("POST", f"/notifications/{notificationName}", params=params if not body else None, json=json_data)
    return data


# --- Execute Shortcut or HomeKit Scene ---
@router.post("/execute")
async def execute_action(
    shortcut: Optional[str] = Query(None, description="Name of iOS shortcut to execute"),
    homekit: Optional[str] = Query(None, description="Name of HomeKit scene to execute"),
    timeout: Optional[int] = Query(None, description="Timeout in seconds (default: 60)"),
    delay: Optional[int] = Query(None, description="Delay execution by N seconds"),
    identifier: Optional[str] = Query(None, description="Unique ID to overwrite pending requests"),
    input: Optional[str] = Query(None, description="Input text for the shortcut"),
    serverId: Optional[str] = Query(None, description="Target specific automation server"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_pushcut_limit),
    body: Optional[dict] = Body(None, description="Full execution payload (overrides query params)"),
):
    """
    Schedule execution of an iOS shortcut or HomeKit scene.

    Provide either 'shortcut' OR 'homekit' parameter (not both).

    Returns 202 Accepted for scheduled requests.

    Example JSON body:
    {
        "shortcut": "My Shortcut",
        "timeout": 120,
        "delay": 5,
        "input": "some value",
        "identifier": "unique-id"
    }
    """
    if not shortcut and not homekit and not body:
        raise HTTPException(status_code=400, detail="Must provide either 'shortcut' or 'homekit' parameter")

    # Build params from query string
    params = {}
    if shortcut:
        params["shortcut"] = shortcut
    if homekit:
        params["homekit"] = homekit
    if timeout:
        params["timeout"] = timeout
    if delay:
        params["delay"] = delay
    if identifier:
        params["identifier"] = identifier
    if input:
        params["input"] = input
    if serverId:
        params["serverId"] = serverId

    # Use JSON body if provided (overrides query params)
    json_data = body if body else None

    status, data = await _pushcut_request("POST", "/execute", params=params if not body else None, json=json_data)
    return data


# --- List Webhook Subscriptions ---
@router.get("/subscriptions")
async def list_subscriptions(
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_pushcut_limit),
):
    """
    List all active webhook subscriptions for online action triggers.

    Returns list of subscription objects with their IDs and webhook URLs.
    """
    status, data = await _pushcut_request("GET", "/subscriptions")
    return data


# --- Register Webhook Subscription ---
@router.post("/subscriptions")
async def create_subscription(
    notificationName: Optional[str] = Query(None, description="Notification to trigger"),
    deviceId: Optional[str] = Query(None, description="Target device ID (omit for all devices)"),
    webhook: Optional[str] = Query(None, description="Webhook URL to register"),
    isLocalUrl: Optional[bool] = Query(None, description="Is webhook on local network"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_pushcut_limit),
    body: Optional[dict] = Body(None, description="Full subscription payload"),
):
    """
    Register a webhook subscription for online action triggers.

    Example JSON body:
    {
        "notificationName": "My Notification",
        "deviceId": "device-123",
        "webhook": "https://example.com/webhook",
        "isLocalUrl": false
    }
    """
    # Build params from query string
    params = {}
    if notificationName:
        params["notificationName"] = notificationName
    if deviceId:
        params["deviceId"] = deviceId
    if webhook:
        params["webhook"] = webhook
    if isLocalUrl is not None:
        params["isLocalUrl"] = str(isLocalUrl).lower()

    # Use JSON body if provided (overrides query params)
    json_data = body if body else None

    status, data = await _pushcut_request("POST", "/subscriptions", params=params if not body else None, json=json_data)
    return data


# --- Delete Webhook Subscription ---
@router.delete("/subscriptions/{subscriptionId}")
async def delete_subscription(
    subscriptionId: str,
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_pushcut_limit),
):
    """
    Remove a webhook subscription by its ID.

    Returns 204 No Content on success.
    """
    status, data = await _pushcut_request("DELETE", f"/subscriptions/{subscriptionId}")
    return data
