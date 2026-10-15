import json
import re
import time
from pathlib import Path
from typing import List, AsyncGenerator, Dict, Any, Optional, Union

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
            if "/shorts/" in parsed.path or "/embed/" in parsed.path or "/live/" in parsed.path:
                parts = parsed.path.strip("/").split("/")
                for p in parts:
                    if len(p) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", p):
                        return p
    except Exception:
        pass

    patterns = [
        r"(?:v=|\/embed\/|\/v\/|youtu\.be\/|\/watch\?v=|\/shorts\/|\/live\/)([0-9A-Za-z_-]{11})",
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

    if hasattr(raw_items, "to_raw_data"):
        raw_items = raw_items.to_raw_data()

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

    try:
        chunk_size = int(get_setting("CHUNK_SIZE", 1000) or 1000)
    except (ValueError, TypeError):
        chunk_size = 1000
    try:
        chunk_overlap = int(get_setting("CHUNK_OVERLAP", 200) or 200)
    except (ValueError, TypeError):
        chunk_overlap = 200

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 5)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = splitter.split_documents([raw_doc])
    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = idx

    # Clear any previous index for this same video to prevent duplicate chunks
    vector_store_manager.delete_document(filename)

    chunks_count = vector_store_manager.add_documents(chunks)
    return {
        "video_id": video_id,
        "filename": filename,
        "url": canonical_url,
        "chunks": chunks_count,
        "total_segments": len(transcript_data)
    }


def load_file_content(file_path: Union[Path, str]) -> List[Document]:
    """Loads a file (PDF, TXT, MD, DOCX, PPTX, XLSX, CSV, JSON) and returns a list of Document objects."""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    filename = file_path.name
    uploaded_at = time.strftime("%Y-%m-%d %H:%M:%S")

    docs: List[Document] = []

    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
            with fitz.open(str(file_path)) as pdf_doc:
                for i, page in enumerate(pdf_doc):
                    text = page.get_text() or ""
                    if text.strip():
                        docs.append(Document(
                            page_content=text,
                            metadata={"source": str(file_path), "filename": filename, "page": i + 1, "file_type": "pdf", "uploaded_at": uploaded_at}
                        ))
        except Exception:
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

        # Traverse document elements in natural sequential order (paragraphs and tables)
        try:
            for child in doc.element.body:
                if child.tag.endswith('p'):
                    p = docx.text.paragraph.Paragraph(child, doc)
                    ptxt = p.text.strip()
                    if ptxt:
                        full_text.append(ptxt)
                elif child.tag.endswith('tbl'):
                    tbl = docx.table.Table(child, doc)
                    for row in tbl.rows:
                        row_cells = []
                        last_val = None
                        for cell in row.cells:
                            ctxt = cell.text.strip().replace('\r', ' ').replace('\n', ' ')
                            if ctxt and ctxt != last_val:
                                row_cells.append(ctxt)
                                last_val = ctxt
                        if row_cells:
                            full_text.append(" | ".join(row_cells))
        except Exception:
            pass

        # Fallback if body iteration produced nothing:
        if not full_text:
            for p in doc.paragraphs:
                if p.text.strip():
                    full_text.append(p.text.strip())
            for tbl in doc.tables:
                for row in tbl.rows:
                    row_cells = [c.text.strip().replace('\n', ' ') for c in row.cells if c.text.strip()]
                    if row_cells:
                        full_text.append(" | ".join(dict.fromkeys(row_cells)))

        content = "\n\n".join(full_text)
        if content.strip():
            docs.append(Document(
                page_content=content,
                metadata={"source": str(file_path), "filename": filename, "file_type": "docx", "uploaded_at": uploaded_at}
            ))

    elif suffix == ".pptx":
        try:
            import pptx
            with open(file_path, "rb") as f:
                prs = pptx.Presentation(f)
                full_text = []
                for slide_idx, slide in enumerate(prs.slides):
                    slide_parts = [f"=== Slide {slide_idx + 1} ==="]
                    for shape in slide.shapes:
                        if shape.has_text_frame:
                            for paragraph in shape.text_frame.paragraphs:
                                ptxt = paragraph.text.strip()
                                if ptxt:
                                    slide_parts.append(ptxt)
                        elif shape.has_table:
                            for row in shape.table.rows:
                                row_cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells if cell.text.strip()]
                                if row_cells:
                                    slide_parts.append(" | ".join(row_cells))
                    if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                        notes = slide.notes_slide.notes_text_frame.text.strip()
                        if notes:
                            slide_parts.append(f"(Speaker Notes: {notes})")
                    if len(slide_parts) > 1:
                        full_text.append("\n".join(slide_parts))
                content = "\n\n".join(full_text)
                if content.strip():
                    docs.append(Document(
                        page_content=content,
                        metadata={"source": str(file_path), "filename": filename, "file_type": "pptx", "uploaded_at": uploaded_at}
                    ))
        except Exception as e:
            print(f"Error parsing PPTX {file_path}: {e}")

    elif suffix in (".xlsx", ".xls"):
        wb = None
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(file_path), data_only=True)
            full_text = []
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                sheet_parts = [f"=== Sheet: {sheet_name} ==="]
                for row in sheet.iter_rows(values_only=True):
                    row_vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
                    if row_vals:
                        sheet_parts.append(" | ".join(row_vals))
                if len(sheet_parts) > 1:
                    full_text.append("\n".join(sheet_parts))
            content = "\n\n".join(full_text)
            if content.strip():
                docs.append(Document(
                    page_content=content,
                    metadata={"source": str(file_path), "filename": filename, "file_type": "xlsx", "uploaded_at": uploaded_at}
                ))
        except Exception as e:
            print(f"Error parsing Excel {file_path}: {e}")
        finally:
            if wb is not None:
                try:
                    wb.close()
                except Exception:
                    pass

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

    try:
        chunk_size = int(get_setting("CHUNK_SIZE", 1000) or 1000)
    except (ValueError, TypeError):
        chunk_size = 1000
    try:
        chunk_overlap = int(get_setting("CHUNK_OVERLAP", 200) or 200)
    except (ValueError, TypeError):
        chunk_overlap = 200

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 5)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks = splitter.split_documents(raw_docs)
    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = idx

    # Clear any previous index for this same filename to prevent duplicates
    vector_store_manager.delete_document(file_path.name)

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
    strict_guardrails: Optional[bool] = None,
    scope: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Executes a guarded RAG query and streams the response via Server-Sent Events (SSE).
    When scope is provided (e.g. 'YouTube: dQw4w9WgXcQ' or 'doc.pdf'), retrieval is strictly
    isolated to that specific document or video, preventing cross-video pollution.
    """
    history = history or []
    sources: List[Dict[str, Any]] = []

    # Check guardrail setting
    from app.config import parse_bool
    if strict_guardrails is None:
        strict_guardrails = parse_bool(get_setting("STRICT_GUARDRAILS", True), default=True)
    else:
        strict_guardrails = parse_bool(strict_guardrails, default=True)

    try:
        # Check if vector store has any indexed documents
        stats = vector_store_manager.get_stats()
        target_scope = scope.strip() if (scope and scope.strip() and scope.strip().lower() != "all") else None

        matching_doc = None
        scope_chunks = 0
        if target_scope:
            matching_doc = next((d for d in stats.get("documents", []) if d.get("filename") == target_scope), None)
            scope_chunks = matching_doc.get("chunks", 0) if matching_doc else 0
            has_docs = (scope_chunks > 0) and use_rag
        else:
            has_docs = (stats.get("total_chunks", 0) > 0) and use_rag

        # Fast Greeting Handling
        if is_simple_greeting(message):
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            if target_scope:
                greeting_reply = (
                    f"Hello! I am your AI assistant dedicated to **{target_scope}**. "
                    "What would you like to know or summarize about this material?"
                )
            elif has_docs:
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

        # If strict guardrails are active with RAG enabled, but no material is loaded
        if strict_guardrails and use_rag:
            if target_scope and scope_chunks == 0:
                yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': f'🛡️ **Guardrail Notice:** No indexed material found for **{target_scope}**. Please verify that the transcript or document is loaded.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
            elif not target_scope and stats.get("total_chunks", 0) == 0:
                yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': '🛡️ **Guardrail Notice:** No YouTube video or documents have been indexed yet. Please provide a YouTube link or upload a file in the sidebar first.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

        context_str = ""
        if has_docs:
            filter_dict = {"filename": target_scope} if target_scope else None
            retrieved_docs = vector_store_manager.search(message, k=8, filter=filter_dict)
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
                        "video_id": meta.get("video_id", ""),
                        "snippet": snippet
                    })

                    loc = f"(Page {page})" if page else f"(Chunk {chunk_idx})"
                    context_parts.append(f"--- Source: {filename} {loc} ---\n{doc.page_content}\n")

                context_str = "\n".join(context_parts)

        # Send retrieved sources to client first
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        # Construct Guarded System Prompt
        item_title = target_scope if target_scope else "the provided YouTube video transcripts and uploaded documents"
        if strict_guardrails and use_rag:
            system_prompt = (
                f"You are an AI assistant grounded strictly in the provided context for: {item_title}.\n\n"
                "### CORE OPERATIONAL DIRECTIVES:\n"
                f"1. GROUNDING & ISOLATION: Answer the user's inquiry thoroughly and accurately using ONLY the provided context below for {item_title}. Do not use or reference other materials or older videos.\n"
                "2. TIMESTAMPS & CITATIONS: When citing information from transcripts or documents, reference timestamps [MM:SS] or chunk sources where available.\n"
                "3. HELPFUL SYNTHESIS: If the user asks for a summary, explanation, key takeaways, or concepts, synthesize a comprehensive and informative answer based on the provided material.\n"
                "4. GUARDRAIL SCOPE POLICY: If and only if the user's question cannot be answered from the provided context or is completely unrelated, politely state:\n"
                f"'{GUARDRAIL_REFUSAL_MSG}'\n"
                "5. FORMATTING: Format all responses in clean, well-structured Markdown with clear headers and bullet points.\n\n"
                f"### Provided Context for {item_title}:\n{context_str}"
            )
        else:
            if has_docs and context_str:
                system_prompt = (
                    f"You are a helpful AI assistant answering questions about {item_title}. "
                    "Use the provided context when applicable, supplemented with your general knowledge when helpful. "
                    "Format your response in clean Markdown.\n\n"
                    f"### Context:\n{context_str}"
                )
            else:
                system_prompt = (
                    "You are a helpful, versatile AI assistant. Answer user questions clearly, thoroughly, and accurately in clean Markdown."
                )

        messages = [SystemMessage(content=system_prompt)]

        # Add recent conversation history (last 6 turns)
        # Avoid duplicating current message if client already included it in history
        valid_history = history[-6:] if history else []
        if valid_history and valid_history[-1].get("role") == "user" and valid_history[-1].get("content") == message:
            valid_history = valid_history[:-1]

        for h in valid_history:
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
            raw_token = chunk.content
            if isinstance(raw_token, list):
                token_str = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in raw_token
                )
            elif not isinstance(raw_token, str):
                token_str = str(raw_token) if raw_token is not None else ""
            else:
                token_str = raw_token

            if token_str:
                yield f"data: {json.dumps({'type': 'token', 'content': token_str})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        error_msg = str(e)
        yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
