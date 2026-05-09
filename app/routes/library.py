# ============================================================
# IMPORTS
# ============================================================
import os
import re
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from typing import Optional
from app.security import get_current_user, require_super_admin
from app.models import User
from app.config import get_key
from app.rate_limit import check_user_rate_limit, APIRateLimiter

# ============================================================
# ROUTER SETUP & CONFIG
# ============================================================
router = APIRouter(prefix="/library", tags=["library"])
logger = logging.getLogger(__name__)

# Open Library public endpoints don't need a key
# S3 (Internet Archive) needs key + secret
S3_KEY = get_key("openlibrary")
S3_SECRET = os.environ.get("OPENLIBRARY_SECRET")

check_library_limit = APIRateLimiter("openlibrary")

# ============================================================
# ROUTE SCHEMA
# ============================================================
# GET    /library/search                       - search books/authors/works
# GET    /library/books                        - book details by ISBN/OCLC/LCCN/OLID
# GET    /library/covers/{type}/{identifier}   - book cover or author photo (returns JPEG)
# GET    /library/works/{work_id}              - work info by OL ID (e.g. OL27448W)
# GET    /library/authors/{author_id}          - author info by OL ID (e.g. OL26320A)
# GET    /library/subjects/{subject}           - books by subject
# GET    /library/archive/capacity             - check Internet Archive upload space
# GET    /library/archive/{bucket}/{file_path} - download file from Internet Archive
# HEAD   /library/archive/{bucket}/{file_path} - file metadata (size, type, etc.)
# DELETE /library/archive/{bucket}/{file_path} - delete file (superAdmin+ only)
#
# Auth: Required (JWT Bearer token)
# DELETE /library/archive/* requires superAdmin or Root
#
# Rate Limits:
#   - User limit:  from role_limits table
#   - API limit:   from api_config table ("openlibrary")
#
# Response:
#   200 - Raw upstream JSON / XML / JPEG depending on endpoint
#   400 - Invalid input (bad ID format, path traversal, etc.)
#   401 - Not authenticated / inactive user
#   429 - Rate limit exceeded
#   502 - Upstream API failed
#   503 - API disabled in config / S3 not configured
# ============================================================

# ============================================================
# INPUT VALIDATION
# ============================================================
def validate_work_id(work_id: str) -> str:
    if not re.match(r'^OL\d+W$', work_id):
        raise HTTPException(400, "Invalid work ID format. Expected: OL{number}W")
    return work_id

def validate_author_id(author_id: str) -> str:
    if not re.match(r'^OL\d+A$', author_id):
        raise HTTPException(400, "Invalid author ID format. Expected: OL{number}A")
    return author_id

def validate_subject(subject: str) -> str:
    if not re.match(r'^[a-zA-Z0-9_-]+$', subject):
        raise HTTPException(400, "Invalid subject. Only alphanumeric, underscore, and hyphen allowed")
    if len(subject) > 100:
        raise HTTPException(400, "Subject too long (max 100 characters)")
    return subject

def validate_file_path(file_path: str) -> str:
    if '..' in file_path or file_path.startswith('/'):
        raise HTTPException(400, "Invalid file path: path traversal not allowed")
    if len(file_path) > 500:
        raise HTTPException(400, "File path too long (max 500 characters)")
    return file_path

# ============================================================
# ENDPOINTS — OPEN LIBRARY
# ============================================================

# --- Search books / authors / works ---
@router.get("/search")
async def search_books(
    q: Optional[str] = Query(None, description="General search query"),
    title: Optional[str] = Query(None, description="Search by title"),
    author: Optional[str] = Query(None, description="Search by author"),
    isbn: Optional[str] = Query(None, description="Search by ISBN"),
    subject: Optional[str] = Query(None, description="Search by subject"),
    page: Optional[int] = Query(1, description="Page number"),
    limit: Optional[int] = Query(10, description="Results per page"),
    sort: Optional[str] = Query(None, description="Sort: new, old, random, key"),
    lang: Optional[str] = Query(None, description="ISO 639-1 language code"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    url = "https://openlibrary.org/search.json"
    params = {"page": page, "limit": limit, "fields": "*,availability"}

    if q:       params["q"] = q
    if title:   params["title"] = title
    if author:  params["author"] = author
    if isbn:    params["isbn"] = isbn
    if subject: params["subject"] = subject
    if sort:    params["sort"] = sort
    if lang:    params["lang"] = lang

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Open Library search API failed")

    return r.json()


# --- Book details by identifier ---
@router.get("/books")
async def get_books(
    bibkeys: str = Query(..., description="Comma-separated IDs, e.g. ISBN:0451526538,OLID:OL123M"),
    format: Optional[str] = Query("json", description="Format: json or javascript"),
    jscmd: Optional[str] = Query("data", description="Output type: viewapi, data, or details"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    url = "https://openlibrary.org/api/books"
    params = {"bibkeys": bibkeys, "format": format, "jscmd": jscmd}

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Open Library books API failed")

    return r.json()


# --- Book cover or author photo (returns JPEG) ---
@router.get("/covers/{type}/{identifier}")
async def get_cover(
    type: str,
    identifier: str,
    size: Optional[str] = Query("M", description="Size: S, M, or L"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    if type.lower() not in ("b", "a"):
        raise HTTPException(400, "Type must be 'b' (book cover) or 'a' (author photo)")
    if size.upper() not in ("S", "M", "L"):
        raise HTTPException(400, "Size must be S, M, or L")

    if ":" in identifier:
        key, value = identifier.split(":", 1)
    else:
        key, value = "id", identifier

    url = f"https://covers.openlibrary.org/{type.lower()}/{key.lower()}/{value}-{size.upper()}.jpg"

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Cover not found or covers API failed")

    return Response(content=r.content, media_type="image/jpeg")


# --- Work info ---
@router.get("/works/{work_id}")
async def get_work(
    work_id: str,
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    work_id = validate_work_id(work_id)
    url = f"https://openlibrary.org/works/{work_id}.json"

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Work not found or API failed")

    return r.json()


# --- Author info ---
@router.get("/authors/{author_id}")
async def get_author(
    author_id: str,
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    author_id = validate_author_id(author_id)
    url = f"https://openlibrary.org/authors/{author_id}.json"

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Author not found or API failed")

    return r.json()


# --- Books by subject ---
@router.get("/subjects/{subject}")
async def get_subject(
    subject: str,
    limit: Optional[int] = Query(12, description="Number of results"),
    offset: Optional[int] = Query(0, description="Offset for pagination"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    subject = validate_subject(subject)
    url = f"https://openlibrary.org/subjects/{subject}.json"
    params = {"limit": limit, "offset": offset}

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Subject not found or API failed")

    return r.json()

# ============================================================
# ENDPOINTS — INTERNET ARCHIVE S3
# ============================================================

# --- Check upload capacity ---
@router.get("/archive/capacity")
async def check_capacity(
    bucket: str = Query(..., description="Item/bucket identifier"),
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    if not S3_KEY or not S3_SECRET:
        raise HTTPException(status_code=503, detail="S3 credentials not configured")

    url = "https://s3.us.archive.org/"
    params = {"check_limit": "1", "accesskey": S3_KEY, "bucket": bucket}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="S3 capacity check failed")

    return Response(content=r.content, media_type="application/xml")


# --- Download file ---
@router.get("/archive/{bucket}/{file_path:path}")
async def get_archive_file(
    bucket: str,
    file_path: str,
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    file_path = validate_file_path(file_path)
    url = f"https://s3.us.archive.org/{bucket}/{file_path}"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(url)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="File not found or S3 API failed")

    content_type = r.headers.get("content-type", "application/octet-stream")
    return Response(content=r.content, media_type=content_type)


# --- File metadata (no download) ---
@router.head("/archive/{bucket}/{file_path:path}")
async def get_archive_metadata(
    bucket: str,
    file_path: str,
    user: User = Depends(get_current_user),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    file_path = validate_file_path(file_path)
    url = f"https://s3.us.archive.org/{bucket}/{file_path}"

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        r = await client.head(url)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="File not found or metadata unavailable")

    return {
        "content_type":   r.headers.get("content-type"),
        "content_length": r.headers.get("content-length"),
        "last_modified":  r.headers.get("last-modified"),
        "etag":           r.headers.get("etag"),
    }


# --- Delete file (superAdmin+ only) ---
@router.delete("/archive/{bucket}/{file_path:path}")
async def delete_archive_file(
    bucket: str,
    file_path: str,
    cascade: Optional[bool] = Query(False, description="Also delete derivative files"),
    user: User = Depends(require_super_admin),
    _user_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_library_limit),
):
    file_path = validate_file_path(file_path)
    logger.info(f"S3 DELETE: user={user.username} bucket={bucket} file={file_path} cascade={cascade}")

    if not S3_KEY or not S3_SECRET:
        raise HTTPException(status_code=503, detail="S3 credentials not configured")

    url = f"https://s3.us.archive.org/{bucket}/{file_path}"
    headers = {"Authorization": f"LOW {S3_KEY}:{S3_SECRET}"}

    if cascade:
        headers["x-archive-cascade-delete"] = "1"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.delete(url, headers=headers)

    if r.status_code not in (200, 204):
        logger.error(f"S3 delete failed for {bucket}/{file_path}: {r.status_code}")
        raise HTTPException(status_code=502, detail="S3 delete operation failed")

    logger.info(f"S3 DELETE SUCCESS: user={user.username} bucket={bucket} file={file_path}")
    return {"status": "deleted", "bucket": bucket, "file": file_path}
