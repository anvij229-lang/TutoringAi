import os
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from app.database.db import get_connection
from app.services.ingestion import ingest_pdf

router = APIRouter(prefix="/api/materials", tags=["materials"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
def upload_material(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No filename provided")
    if Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(400, "Day 1 supports PDF files only")

    safe_name = Path(file.filename).name
    dest = UPLOAD_DIR / safe_name
    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    try:
        result = ingest_pdf(str(dest), Path(safe_name).stem, safe_name)
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/{material_id}/chunks")
def get_chunks(material_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, content, page_number, chunk_index FROM chunks "
                "WHERE material_id = %s ORDER BY page_number, chunk_index LIMIT 20",
                (material_id,),
            )
            rows = cur.fetchall()
    return [
        {"id": str(r[0]), "content": r[1], "page_number": r[2], "chunk_index": r[3]}
        for r in rows
    ]