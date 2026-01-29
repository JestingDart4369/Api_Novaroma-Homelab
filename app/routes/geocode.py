import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from app.security import get_current_user
from app.models import User

router = APIRouter(tags=["geocode"])
GEOAPIFY_KEY = os.environ["GEOAPIFY_KEY"]

@router.get("/geocode")
async def geocode(text: str, user: User = Depends(get_current_user)):
    url = "https://api.geoapify.com/v1/geocode/search"
    params = {"text": text, "apiKey": GEOAPIFY_KEY, "limit": 1}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream geocode API failed")

    data = r.json()
    features = data.get("features", [])
    if not features:
        return {"found": False, "user": user.username, "source": "geoapify"}

    props = features[0].get("properties", {})
    return {
        "found": True,
        "lat": props.get("lat"),
        "lon": props.get("lon"),
        "formatted": props.get("formatted"),
        "user": user.username,
        "source": "geoapify",
    }
