import json
import re
import time
from pathlib import Path
from typing import List, AsyncGenerator, Dict, Any, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.config import get_setting
from app.core.model_factory import get_llm
from app.core.vector_store import vector_store_manager

# Guardrail refusal message standard
GUARDRAIL_REFUSAL_MSG = (
    "🛡️ **Guardrail Notice:** I can only answer questions related to the provided YouTube video "
    "and uploaded documents. This question is outside the scope of the provided material."
)


def extract_youtube_video_id(url: str) -> Optional[str]:
    """Extracts the 11-character YouTube video ID from various URL formats."""
    url = url.strip()
    if not url:
        return None

    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
        return url

    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        if "youtube" in parsed.netloc or "youtu.be" in parsed.netloc:
            qs = parse_qs(parsed.query)
            if "v" in qs and len(qs["v"]) > 0:
                return qs["v"][0]
            if parsed.netloc == "youtu.be" and parsed.path:
                vid = parsed.path.strip("/").split("/")[0]
                if len(vid) == 11:
                    return vid
            if "/shorts/" in parsed.path or "/embed/" in parsed.path:
                parts = parsed.path.strip("/").split("/")
                for p in parts:
                    if len(p) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", p):
                        return p
    except Exception:
        pass

    patterns = [
        r"(?:v=|\/embed\/|\/v\/|youtu\.be\/|\/watch\?v=|\/shorts\/)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_youtube_raw_transcript(video_id: str) -> List[Dict[str, Any]]:
    """
    Universally fetches transcript items supporting youtube_transcript_api v1.0+ and legacy versions.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    raw_items = []
    error_reasons = []

    # 1. Try modern API: instance with .fetch() or .list()
    try:
        api = YouTubeTranscriptApi() if isinstance(YouTubeTranscriptApi, type) else YouTubeTranscriptApi
        if hasattr(api, "fetch"):
            try:
                raw_items = api.fetch(video_id)
            except Exception as e:
                error_reasons.append(str(e))
                if hasattr(api, "list"):
                    try:
                        transcript_list = api.list(video_id)
                        try:
                            t_obj = transcript_list.find_transcript(["en", "en-US", "en-GB"])
                        except Exception:
                            t_obj = next(iter(transcript_list))
                        raw_items = t_obj.fetch() if hasattr(t_obj, "fetch") else t_obj
                    except Exception as e2:
                        error_reasons.append(str(e2))
    except Exception as e:
        error_reasons.append(str(e))

    # 2. Try legacy API: YouTubeTranscriptApi.get_transcript
    if not raw_items and hasattr(YouTubeTranscriptApi, "get_transcript"):
        try:
            raw_items = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as e:
            error_reasons.append(str(e))

    if not raw_items:
        reason_str = " | ".join(error_reasons) if error_reasons else "No captions found"
        raise RuntimeError(
            f"Could not retrieve transcript for video ({video_id}). "
            f"Please verify that captions/subtitles are enabled on this video. Details: {reason_str}"
        )

    normalized = []
    for item in raw_items:
        if isinstance(item, dict):
            text = item.get("text", "")
            start = float(item.get("start", 0.0))
        else:
            text = getattr(item, "text", "")
            start = float(getattr(item, "start", 0.0))
        if text and text.strip():
            normalized.append({"text": text.strip(), "start": start})

    return normalized


def format_timestamp(seconds: float) -> str:
    """Formats float seconds into [MM:SS] or [HH:MM:SS]."""
    total_sec = int(seconds)
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def process_and_index_youtube(url: str) -> Dict[str, Any]:
    """
    Fetches transcript from a YouTube video URL using universal transcript fetcher,
    formats timestamped text segments, chunks the content, and indexes into ChromaDB.
    """
    video_id = extract_youtube_video_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please provide a valid watch link or video ID.")

    transcript_data = fetch_youtube_raw_transcript(video_id)
    if not transcript_data:
        raise ValueError("The YouTube video transcript is empty or unavailable.")

    uploaded_at = time.strftime("%Y-%m-%d %H:%M:%S")
    filename = f"YouTube: {video_id}"
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"

    # Group transcript into timestamped paragraphs
    formatted_parts = []
    current_segment = []
    current_start = 0.0

    for idx, item in enumerate(transcript_data):
        text = item.get("text", "").strip()
        start = item.get("start", 0.0)
        if not current_segment:
            current_start = start
        current_segment.append(text)

        # Break every ~4 items or ~200 characters for localized timestamp tags
        if len(current_segment) >= 5 or len(" ".join(current_segment)) > 250:
            ts_str = format_timestamp(current_start)
            formatted_parts.append(f"[{ts_str}] " + " ".join(current_segment))
            current_segment = []

    if current_segment:
        ts_str = format_timestamp(current_start)
        formatted_parts.append(f"[{ts_str}] " + " ".join(current_segment))

    full_transcript_text = "\n\n".join(formatted_parts)

    raw_doc = Document(
        page_content=full_transcript_text,
        metadata={
            "source": canonical_url,
            "filename": filename,
            "file_type": "youtube",
            "video_id": video_id,
            "uploaded_at": uploaded_at
        }
    )

    chunk_size = int(get_setting("CHUNK_SIZE", 1000))
    chunk_overlap = int(get_setting("CHUNK_OVERLAP", 200))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = splitter.split_documents([raw_doc])
    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = idx

    chunks_count = vector_store_manager.add_documents(chunks)
    return {
        "video_id": video_id,
        "filename": filename,
        "url": canonical_url,
        "chunks": chunks_count,
        "total_segments": len(transcript_data)
    }


def load_file_content(file_path: Path) -> List[Document]:
    """Loads a file (PDF, TXT, MD, DOCX, CSV) and returns a list of Document objects."""
    suffix = file_path.suffix.lower()
    filename = file_path.name
    uploaded_at = time.strftime("%Y-%m-%d %H:%M:%S")

    docs: List[Document] = []

    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                docs.append(Document(
                    page_content=text,
                    metadata={"source": str(file_path), "filename": filename, "page": i + 1, "file_type": "pdf", "uploaded_at": uploaded_at}
                ))

    elif suffix == ".docx":
        import docx
        doc = docx.Document(str(file_path))
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
        content = "\n".join(full_text)
        if content.strip():
            docs.append(Document(
                page_content=content,
                metadata={"source": str(file_path), "filename": filename, "file_type": "docx", "uploaded_at": uploaded_at}
            ))

    elif suffix in (".txt", ".md", ".csv", ".json", ".py", ".js", ".html"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if content.strip():
                docs.append(Document(
                    page_content=content,
                    metadata={"source": str(file_path), "filename": filename, "file_type": suffix[1:], "uploaded_at": uploaded_at}
                ))

    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if content.strip():
                docs.append(Document(
                    page_content=content,
                    metadata={"source": str(file_path), "filename": filename, "file_type": "text", "uploaded_at": uploaded_at}
                ))

    return docs


def process_and_index_document(file_path: Path) -> int:
    """Loads, splits, and embeds a document into ChromaDB."""
    raw_docs = load_file_content(file_path)
    if not raw_docs:
        return 0

    chunk_size = int(get_setting("CHUNK_SIZE", 1000))
    chunk_overlap = int(get_setting("CHUNK_OVERLAP", 200))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks = splitter.split_documents(raw_docs)
    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = idx

    return vector_store_manager.add_documents(chunks)


def is_simple_greeting(text: str) -> bool:
    """Checks if input is a polite conversational greeting."""
    clean = re.sub(r"[^\w\s]", "", text.strip().lower())
    greetings = {"hi", "hello", "hey", "good morning", "good evening", "good afternoon", "greetings", "help"}
    return clean in greetings


async def stream_rag_chat(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    use_rag: bool = True,
    strict_guardrails: Optional[bool] = None
) -> AsyncGenerator[str, None]:
    """
    Executes a guarded RAG query and streams the response via Server-Sent Events (SSE).
    Strictly prevents off-topic answering when guardrails are active.
    """
    history = history or []
    sources: List[Dict[str, Any]] = []

    # Check guardrail setting
    if strict_guardrails is None:
        strict_guardrails = bool(get_setting("STRICT_GUARDRAILS", True))

    try:
        # Check if vector store has any indexed documents
        stats = vector_store_manager.get_stats()
        has_docs = stats["total_chunks"] > 0 and use_rag

        # Fast Greeting Handling
        if is_simple_greeting(message):
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            if has_docs:
                greeting_reply = (
                    "Hello! I am your AI assistant strictly grounded in the provided YouTube video "
                    "and document context. What would you like to know about the material?"
                )
            else:
                greeting_reply = (
                    "Hello! Please add a YouTube video URL or upload documents in the sidebar "
                    "so I can answer your questions based on that content."
                )
            yield f"data: {json.dumps({'type': 'token', 'content': greeting_reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # If guardrails are active but no material is loaded
        if strict_guardrails and not has_docs:
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': '🛡️ **Guardrail Notice:** No YouTube video or documents have been indexed yet. Please provide a YouTube link or upload a file first.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        context_str = ""
        if has_docs:
            retrieved_docs = vector_store_manager.search(message, k=4)
            if retrieved_docs:
                context_parts = []
                for i, doc in enumerate(retrieved_docs):
                    meta = doc.metadata
                    filename = meta.get("filename", "Document")
                    page = meta.get("page", None)
                    chunk_idx = meta.get("chunk_index", 0)
                    file_type = meta.get("file_type", "")
                    snippet = doc.page_content.strip()[:240] + ("..." if len(doc.page_content) > 240 else "")
                    
                    sources.append({
                        "id": i + 1,
                        "filename": filename,
                        "page": page,
                        "chunk": chunk_idx,
                        "file_type": file_type,
                        "snippet": snippet
                    })
                    
                    loc = f"(Page {page})" if page else f"(Chunk {chunk_idx})"
                    context_parts.append(f"--- Source: {filename} {loc} ---\n{doc.page_content}\n")

                context_str = "\n".join(context_parts)

        # Send retrieved sources to client first
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        # Construct Guarded System Prompt
        if strict_guardrails:
            system_prompt = (
                "You are a strictly guarded AI assistant dedicated ONLY to the provided context from the user's "
                "YouTube video transcripts and uploaded documents.\n\n"
                "### CRITICAL GUARDRAIL DIRECTIVES (MANDATORY):\n"
                "1. STRICT REFUSAL POLICY: If the user's question is NOT directly answered by or clearly relevant to "
                "the provided context, you MUST STRICTLY REFUSE to answer.\n"
                "2. EXACT REFUSAL TEXT: When refusing, respond EXACTLY with:\n"
                f"'{GUARDRAIL_REFUSAL_MSG}'\n"
                "3. NO OUTSIDE KNOWLEDGE: Even if you know the answer to general questions (e.g. general trivia, coding tasks, "
                "world history, unrelated topics), NEVER answer them. Refuse immediately.\n"
                "4. FACTUALITY: Only state information that is directly supported by the context below. Do not guess or extrapolate.\n"
                "5. FORMATTING: Format valid answers in clean, professional Markdown.\n\n"
                f"### Provided Context:\n{context_str}"
            )
        else:
            if has_docs and context_str:
                system_prompt = (
                    "You are a helpful AI assistant. Answer the user's question using the provided context when applicable. "
                    "If the answer is not in the context, you may answer using general knowledge while indicating so.\n\n"
                    f"### Context:\n{context_str}"
                )
            else:
                system_prompt = (
                    "You are a helpful AI assistant. Answer user questions clearly and concisely in clean Markdown."
                )

        messages = [SystemMessage(content=system_prompt)]

        # Add recent conversation history (last 6 turns)
        for h in history[-6:]:
            role = h.get("role")
            content = h.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=message))

        # Stream LLM output
        llm = get_llm(provider=provider, model=model, temperature=temperature, streaming=True)
        async for chunk in llm.astream(messages):
            token = chunk.content
            if token:
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        error_msg = str(e)
        yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
