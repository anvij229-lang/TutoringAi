from fastapi import APIRouter
from app.database.db import get_connection

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health")
def health_check():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                ok = cur.fetchone()[0] == 1
        return {"status": "ok", "database": ok}
    except Exception as e:
        return {"status": "error", "database": False, "error": str(e)}