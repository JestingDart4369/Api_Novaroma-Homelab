# ============================================================
# IMPORTS
# ============================================================
import httpx
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.security import get_current_user
from app.models import User
from app.rate_limit import check_user_rate_limit, APIRateLimiter

# ============================================================
# ROUTER SETUP & CONFIG
# ============================================================
router = APIRouter(prefix="/grade", tags=["grade"])

check_grade_limit = APIRateLimiter("grade")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# POST   /grade/user/auth     - login with grade account credentials
# GET    /grade/user          - get current grade user info
# PATCH  /grade/user          - change username or password
# DELETE /grade/user          - delete grade account
# POST   /grade/user          - register new grade account
#
# GET    /grade/subjects       - list all subjects (or one if subject_id given)
# POST   /grade/subjects       - create subject
# PUT    /grade/subjects       - update subject
# DELETE /grade/subjects       - delete subject
#
# GET    /grade/exam           - list all exams (or one if exam_id given)
# POST   /grade/exams          - create exam
# PUT    /grade/exams          - update exam
# DELETE /grade/exams          - delete exam
# GET    /grade/subjects/exams - list all exams for a subject
#
# Auth: Required (JWT Bearer token)
# Rate Limits:
#   - User limit: from role_limits table
#   - API limit:  from api_config table ("grade")
# ============================================================

class AuthRequest(BaseModel):
    user: str
    password: str

# ============================================================
# ENDPOINTS
# ============================================================

# --- User Login ---
@router.post("/user/auth")
async def auth(
    body: AuthRequest,
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = "https://api.sercraft.ch/login"

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json={"user": body.user, "password": body.password})

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")

    return r.json()


# --- Get Current User Info ---
@router.get("/user")
async def get_current_user_info(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = "https://api.sercraft.ch/user"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers={"x-access-token": grade_token})

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Change Username or Password ---
@router.patch("/user")
async def change_current_user_info(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    new_password: str = Query(None, description="Change password of the Account"),
    new_username: str = Query(None, description="Change username of the Account"),
    password: str = Query(..., description="Current Password"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = "https://api.sercraft.ch/user"
    if new_password is not None:
        update_password_url = f"{url}/update_password"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.put(update_password_url, headers={"x-access-token": grade_token}, json={"old_password": password, "new_password": new_password})

    elif new_username is not None:
        update_username_url = f"{url}/update_username"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.put(update_username_url, headers={"x-access-token": grade_token}, json={"username": new_username, "password": password})

    else:
        raise HTTPException(status_code=400, detail="No changes specified")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Delete Grade Account ---
@router.delete("/user")
async def delete_current_user(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = "https://api.sercraft.ch/user"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.delete(url, headers={"x-access-token": grade_token})
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Register New Grade Account ---
@router.post("/user")
async def create_user(
    username: str = Query(..., description="Username of the new Account"),
    password: str = Query(..., description="Password of the new Account"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = "https://api.sercraft.ch/register"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json={"user": username, "password": password})
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Get Subjects ---
@router.get("/subjects")
async def get_subjects(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    subject_id: str = Query(None, description="ID of the Subject"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = "https://api.sercraft.ch/subjects"
    if subject_id is not None:
        url = f"{url}/{subject_id}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers={"x-access-token": grade_token})
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Create Subject ---
@router.post("/subjects")
async def create_subject(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    name: str = Query(..., description="Name of the new Subject"),
    average: float = Query(None, description="Average of the new Subject"),
    points: float = Query(None, description="Points of the new Subject"),
    num_exams: int = Query(None, description="Number of exams of the new Subject"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = "https://api.sercraft.ch/subjects"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers={"x-access-token": grade_token}, json={"name": name, "average": average, "points": points, "num_exams": num_exams})
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Update Subject ---
@router.put("/subjects")
async def update_subject(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    subject_id: str = Query(..., description="ID of the Subject"),
    name: str = Query(None, description="Name of the Subject"),
    average: float = Query(None, description="Average of the Subject"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    if name is None and average is None:
        raise HTTPException(status_code=400, detail="No changes specified")

    url = f"https://api.sercraft.ch/subjects/{subject_id}"
    body = {}
    if name is not None:
        body["name"] = name
    if average is not None:
        body["average"] = average

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.put(url, headers={"x-access-token": grade_token}, json=body)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Delete Subject ---
@router.delete("/subjects")
async def delete_subject(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    subject_id: str = Query(..., description="ID of the Subject"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = f"https://api.sercraft.ch/subjects/{subject_id}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.delete(url, headers={"x-access-token": grade_token})
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Get Exams ---
@router.get("/exam")
async def get_exams(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    exam_id: str = Query(None, description="ID of the Exam"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    if exam_id is not None:
        url = f"https://api.sercraft.ch/grades/{exam_id}"
    else:
        url = "https://api.sercraft.ch/grades"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers={"x-access-token": grade_token})
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Create Exam ---
@router.post("/exams")
async def create_exam(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    subject_id: str = Query(..., description="ID of the Subject"),
    name: str = Query(..., description="Name of the Exam"),
    grade: str = Query(..., description="Grade received"),
    weight: str = Query(..., description="Weight of the Exam"),
    details: str = Query(..., description="Additional details"),
    date: str = Query(None, description="Date of the Exam (YYYY-MM-DD), defaults to today"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = "https://api.sercraft.ch/grades"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers={"x-access-token": grade_token}, json={
            "subject_id": subject_id,
            "name": name,
            "grade": grade,
            "weight": weight,
            "details": details,
            "date": date or datetime.now().strftime("%Y-%m-%d"),
        })
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Get Exams for a Subject ---
@router.get("/subjects/exams")
async def get_subject_exams(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    subject_id: str = Query(..., description="ID of the Subject"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = f"https://api.sercraft.ch/subjects/{subject_id}/grades"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers={"x-access-token": grade_token})
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Update Exam ---
@router.put("/exams")
async def update_exam(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    exam_id: str = Query(..., description="ID of the Exam"),
    name: str = Query(None, description="Name of the Exam"),
    grade: str = Query(None, description="Grade received"),
    weight: str = Query(None, description="Weight of the Exam"),
    details: str = Query(None, description="Additional details"),
    date: str = Query(None, description="Date of the Exam (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    if not any([name, grade, weight, details, date]):
        raise HTTPException(status_code=400, detail="No changes specified")

    url = f"https://api.sercraft.ch/grades/{exam_id}"
    body = {}
    if name is not None:
        body["name"] = name
    if grade is not None:
        body["grade"] = grade
    if weight is not None:
        body["weight"] = weight
    if details is not None:
        body["details"] = details
    if date is not None:
        body["date"] = date

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.put(url, headers={"x-access-token": grade_token}, json=body)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()


# --- Delete Exam ---
@router.delete("/exams")
async def delete_exam(
    grade_token: str = Query(..., alias="X-Grade-Token"),
    exam_id: str = Query(..., description="ID of the Exam"),
    current_user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_grade_limit),
):
    url = f"https://api.sercraft.ch/grades/{exam_id}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.delete(url, headers={"x-access-token": grade_token})
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Upstream Grades API failed")
    return r.json()
