from fastapi import APIRouter
from app.routes.settings import users, apis, roles, software, hardware

router = APIRouter(prefix="/settings", tags=["settings"])
router.include_router(users.router)
router.include_router(apis.router)
router.include_router(roles.router)
router.include_router(software.router)
router.include_router(hardware.router)
