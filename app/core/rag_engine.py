import json
import time
from pathlib import Path
from typing import List, AsyncGenerator, Dict, Any, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.config import get_setting
from app.core.model_factory import get_llm
from app.core.vector_store import vector_store_manager


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
        # Fallback raw text read
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


async def stream_rag_chat(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    use_rag: bool = True
) -> AsyncGenerator[str, None]:
    """
    Executes a RAG query and streams the response via Server-Sent Events (SSE).
    Yields format:
      data: {"type": "sources", "sources": [...]} \n\n
      data: {"type": "token", "content": "..."} \n\n
      data: {"type": "done"} \n\n
    """
    history = history or []
    sources: List[Dict[str, Any]] = []

    try:
        # Check if vector store has any indexed documents
        stats = vector_store_manager.get_stats()
        has_docs = stats["total_chunks"] > 0 and use_rag

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
                    snippet = doc.page_content.strip()[:240] + ("..." if len(doc.page_content) > 240 else "")
                    
                    sources.append({
                        "id": i + 1,
                        "filename": filename,
                        "page": page,
                        "chunk": chunk_idx,
                        "snippet": snippet
                    })
                    
                    loc = f"(Page {page})" if page else f"(Chunk {chunk_idx})"
                    context_parts.append(f"--- Document: {filename} {loc} ---\n{doc.page_content}\n")

                context_str = "\n".join(context_parts)

        # Send retrieved sources to client first
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        # Construct System Prompt & Messages
        if has_docs and context_str:
            system_prompt = (
                "You are an intelligent, accurate AI assistant. You have access to the user's uploaded documents.\n"
                "Use the following retrieved context to answer the user's questions clearly, concisely, and factually.\n"
                "If the context does not contain enough information to answer, state honestly that the documents don't specify, "
                "then answer to the best of your knowledge if appropriate.\n"
                "Always format your answers in clean Markdown.\n\n"
                f"### Retrieved Context:\n{context_str}"
            )
        else:
            system_prompt = (
                "You are a helpful, brilliant AI assistant. You answer user questions clearly, concisely, "
                "and formatted in clean Markdown with code blocks when applicable."
            )

        messages = [SystemMessage(content=system_prompt)]

        # Add recent conversation history (last 8 turns)
        for h in history[-8:]:
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
