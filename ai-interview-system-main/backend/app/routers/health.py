from fastapi import APIRouter

from app.database.mongo import db_manager


router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "database_mode": db_manager.mode,
    }
