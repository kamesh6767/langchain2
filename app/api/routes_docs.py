import shutil
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException

from pydantic import BaseModel
from app.config import UPLOADS_DIR
from app.core.rag_engine import process_and_index_document, process_and_index_youtube
from app.core.vector_store import vector_store_manager

router = APIRouter(prefix="/api/docs", tags=["Documents"])


class YouTubeIndexRequest(BaseModel):
    url: str


@router.get("")
async def get_documents_status() -> Dict[str, Any]:
    """Retrieves statistics on currently indexed documents and chunks."""
    return vector_store_manager.get_stats()


@router.post("/upload")
async def upload_and_index_documents(files: List[UploadFile] = File(...)):
    """Uploads one or multiple documents, saves them, and indexes chunks into ChromaDB."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    results = []
    for file in files:
        raw_name = file.filename or "uploaded_file"
        filename = Path(raw_name).name  # Sanitize against path traversal attacks
        dest_path = UPLOADS_DIR / filename

        try:
            with open(dest_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            chunks_indexed = process_and_index_document(dest_path)
            results.append({
                "filename": filename,
                "chunks": chunks_indexed,
                "success": True,
                "message": f"Successfully indexed {chunks_indexed} chunks."
            })
        except Exception as e:
            results.append({
                "filename": filename,
                "chunks": 0,
                "success": False,
                "error": str(e)
            })

    return {"uploaded": results, "stats": vector_store_manager.get_stats()}


@router.post("/youtube")
async def index_youtube_video(payload: YouTubeIndexRequest):
    """Fetches transcript for a YouTube video URL and indexes it into ChromaDB."""
    try:
        result = process_and_index_youtube(payload.url)
        return {
            "success": True,
            "video": result,
            "stats": vector_store_manager.get_stats()
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{filename:path}")
async def delete_document(filename: str):
    """Removes a document from the vector store and disk."""
    import urllib.parse
    filename = urllib.parse.unquote(filename)
    success = vector_store_manager.delete_document(filename)
    try:
        sanitized_name = Path(filename).name
        dest_path = (UPLOADS_DIR / sanitized_name).resolve()
        if dest_path.is_file() and dest_path.is_relative_to(UPLOADS_DIR.resolve()):
            dest_path.unlink()
    except Exception as e:
        print(f"File delete note for {filename}: {e}")

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete document from vector index.")

    return {"success": True, "filename": filename, "stats": vector_store_manager.get_stats()}


@router.delete("")
async def clear_all_documents():
    """Wipes the entire vector store index and uploads folder."""
    vector_store_manager.clear_all()
    if UPLOADS_DIR.exists():
        for item in UPLOADS_DIR.iterdir():
            try:
                if item.is_file():
                    item.unlink()
            except Exception as e:
                print(f"Error clearing upload {item}: {e}")

    return {"success": True, "message": "All documents and vector indices cleared."}
