import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.database.db import get_connection
from app.services.ingestion import ingest_file

router = APIRouter(prefix="/api/materials", tags=["materials"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

FILE_TYPES = {
".pdf": "pdf",
".pptx": "pptx",
".mp4": "video",
".mov": "video",
".mkv": "video",
".webm": "video",
".m4v": "video",
}

MAX_MB = {
"pdf": int(os.getenv("MAX_DOC_MB", "30")),
"pptx": int(os.getenv("MAX_DOC_MB", "30")),
"video": int(os.getenv("MAX_VIDEO_MB", "200")),
}


def save_upload(file: UploadFile, destination: Path, max_mb: int):
    max_bytes = max_mb * 1024 * 1024
    written = 0
    with destination.open("wb") as buffer:
        while True:
            block = file.file.read(1024 * 1024)
            if not block:
                break
            written += len(block)
            if written > max_bytes:
                break
            buffer.write(block)
    if written > max_bytes:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail=f"File is too large (max {max_mb} MB)")


@router.post("/upload")
def upload_material(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    safe_name = Path(file.filename).name
    file_type = FILE_TYPES.get(Path(safe_name).suffix.lower())
    if file_type is None:
        raise HTTPException(
            status_code=400,
            detail="Supported files: PDF, PPTX and video (MP4, MOV, MKV, WEBM, M4V)",
        )

    destination = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    save_upload(file, destination, MAX_MB[file_type])

    try:
        result = ingest_file(str(destination), Path(safe_name).stem, safe_name, file_type)
        return {"success": True, **result}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    finally:
        if file_type == "video":
            destination.unlink(missing_ok=True)

@router.get("/{material_id}/chunks")
def get_chunks(material_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, content, page_number, start_seconds, chunk_index FROM chunks "
                "WHERE material_id = %s ORDER BY page_number, start_seconds, chunk_index LIMIT 20",
                (material_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": str(r[0]),
            "content": r[1],
            "page_number": r[2],
            "start_seconds": r[3],
            "chunk_index": r[4],
        }
        for r in rows
    ]