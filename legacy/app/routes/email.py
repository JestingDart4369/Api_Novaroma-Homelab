# ============================================================
# IMPORTS
# ============================================================
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from app.security import get_current_user
from app.models import User
from app.config import get_key
from app.rate_limit import check_user_rate_limit, APIRateLimiter

# ============================================================
# ROUTER SETUP & CONFIG
# ============================================================
router = APIRouter(prefix="/email", tags=["email"])

check_resend_limit = APIRateLimiter("resend")

# Resend SDK — optional import, graceful fallback if not installed
try:
    import resend
    resend.api_key = get_key("resend")
    RESEND_AVAILABLE = True
except (ImportError, ValueError):
    RESEND_AVAILABLE = False

# ============================================================
# ROUTE SCHEMA
# ============================================================
# POST /email/send        - send email with full control (to, from, subject, html)
# POST /email/send-simple - send email with simplified addressing (domain is server-configured)
#
# Auth: Required (JWT Bearer token)
#
# Rate Limits:
#   - User limit:  from role_limits table
#   - API limit:   from api_config table ("resend")
#
# Response:
#   200 - { success, email_id, to, user }
#   401 - Not authenticated / inactive user
#   429 - Rate limit exceeded
#   501 - resend package not installed
#   502 - Resend API call failed
#   503 - API disabled in config
# ============================================================

# ============================================================
# PYDANTIC MODELS
# ============================================================
class EmailRequest(BaseModel):
    to: List[EmailStr]
    subject: str
    html: str
    from_email: Optional[str] = None  # falls back to DEFAULT_FROM_EMAIL

class SimpleEmailRequest(BaseModel):
    to_users: List[str]       # usernames only — domain added server-side
    subject: str
    html: str
    from_name: Optional[str] = None  # e.g. "MyApp" → "MyApp <myapp@domain.com>"

# ============================================================
# ENDPOINTS
# ============================================================

# --- Full email (caller controls from + to) ---
@router.post("/send")
async def send_email(
    body: EmailRequest,
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_resend_limit),
):
    if not RESEND_AVAILABLE:
        raise HTTPException(status_code=501, detail="Email service not available. Install 'resend' package.")

    from_email = body.from_email or os.environ.get("DEFAULT_FROM_EMAIL", "noreply@api.novaroma-homelab.uk")

    try:
        result = resend.Emails.send({
            "from":    from_email,
            "to":      body.to,
            "subject": body.subject,
            "html":    body.html,
        })
        return {"success": True, "email_id": result.get("id"), "to": body.to, "user": user.username}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {str(e)}")


# --- Simplified email (domain pre-configured, caller only gives usernames) ---
@router.post("/send-simple")
async def send_simple_email(
    body: SimpleEmailRequest,
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_resend_limit),
):
    if not RESEND_AVAILABLE:
        raise HTTPException(status_code=501, detail="Email service not available. Install 'resend' package.")

    # Recipient domain (e.g., novaroma-homelab.uk)
    recipient_domain = os.environ.get("EMAIL_DOMAIN", "novaroma-homelab.uk")
    to_addresses = [f"{u}@{recipient_domain}" for u in body.to_users]

    # Sender domain (e.g., api.novaroma-homelab.uk - verified in Resend)
    sender_domain = os.environ.get("SENDER_DOMAIN", "api.novaroma-homelab.uk")
    default_from = os.environ.get("DEFAULT_FROM_EMAIL", f"noreply@{sender_domain}")

    if body.from_name:
        # Use custom display name but keep verified sender email from DEFAULT_FROM_EMAIL
        # This prevents "music@api.novaroma-homelab.uk" which isn't verified
        if "<" in default_from and ">" in default_from:
            email_part = default_from.split("<")[1].split(">")[0].strip()
        else:
            email_part = default_from.strip()
        from_email = f"{body.from_name} <{email_part}>"
    else:
        from_email = default_from

    try:
        result = resend.Emails.send({
            "from":    from_email,
            "to":      to_addresses,
            "subject": body.subject,
            "html":    body.html,
        })
        return {"success": True, "email_id": result.get("id"), "to": to_addresses, "from": from_email, "user": user.username}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {str(e)}")
