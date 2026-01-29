import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from app.security import get_current_user
from app.models import User

router = APIRouter(tags=["weather"])
OPENWEATHER_KEY = os.environ["OPENWEATHER_KEY"]

@router.get("/weather")
async def weather(city: str, user: User = Depends(get_current_user)):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": OPENWEATHER_KEY, "units": "metric"}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream weather API failed")

    raw = r.json()
    return {
        "city": raw.get("name"),
        "temp_c": raw["main"]["temp"],
        "humidity": raw["main"]["humidity"],
        "desc": raw["weather"][0]["description"],
        "user": user.username,
        "source": "openweather",
    }
