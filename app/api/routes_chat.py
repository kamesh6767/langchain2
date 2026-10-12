from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict

from app.core.rag_engine import stream_rag_chat

router = APIRouter(prefix="/api/chat", tags=["Chat"])


class ChatStreamRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    use_rag: bool = True
    strict_guardrails: Optional[bool] = None


@router.post("/stream")
async def chat_stream_endpoint(payload: ChatStreamRequest):
    """
    Streams LLM conversational output with RAG context and source citations via SSE.
    """
    return StreamingResponse(
        stream_rag_chat(
            message=payload.message,
            history=payload.history,
            provider=payload.provider,
            model=payload.model,
            temperature=payload.temperature,
            use_rag=payload.use_rag,
            strict_guardrails=payload.strict_guardrails
        ),
        media_type="text/event-stream"
    )
