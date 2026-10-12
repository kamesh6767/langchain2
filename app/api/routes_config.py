from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.config import get_public_settings, save_settings, get_api_key
from app.core.model_factory import test_connection

router = APIRouter(prefix="/api/config", tags=["Configuration"])


class SettingsUpdateRequest(BaseModel):
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    DEFAULT_LLM_PROVIDER: Optional[str] = None
    DEFAULT_LLM_MODEL: Optional[str] = None
    DEFAULT_EMBEDDING_PROVIDER: Optional[str] = None
    DEFAULT_EMBEDDING_MODEL: Optional[str] = None
    CHUNK_SIZE: Optional[int] = None
    CHUNK_OVERLAP: Optional[int] = None
    TEMPERATURE: Optional[float] = None


class TestConnectionRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None


@router.get("")
async def get_config() -> Dict[str, Any]:
    """Retrieves current public configuration and masked keys status."""
    return get_public_settings()


@router.post("")
async def update_config(payload: SettingsUpdateRequest) -> Dict[str, Any]:
    """Updates API keys and model preferences, saving persistently."""
    updates = payload.model_dump(exclude_unset=True)
    return save_settings(updates)


@router.post("/test")
async def test_provider_key(payload: TestConnectionRequest):
    """Validates an API key against the provider API."""
    provider = payload.provider.lower().strip()
    key = payload.api_key.strip() if payload.api_key else get_api_key(provider)
    if not key:
        raise HTTPException(status_code=400, detail=f"No API key provided or found for {provider}.")
    
    success, message = await test_connection(provider, key)
    return {"success": success, "message": message}
