import math
import hashlib
import re
from typing import Optional, Tuple, List
from app.config import get_api_key, get_setting


class LightweightLocalEmbeddings:
    """
    Zero-dependency, fast, local CPU embeddings using feature hashing & TF-IDF.
    Ensures document and YouTube indexing works 100% reliably out-of-the-box
    even when using LLM providers without an embedding API (such as Groq).
    """
    def __init__(self, dim: int = 256):
        self.dim = dim

    def _embed(self, text: str) -> List[float]:
        words = re.findall(r"\w+", text.lower())
        if not words:
            return [0.0] * self.dim
        vec = [0.0] * self.dim
        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[h] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


def get_embeddings(provider: Optional[str] = None, model: Optional[str] = None):
    """
    Returns the appropriate LangChain Embeddings instance based on configuration.
    Priority:
    - If provider is explicitly specified ('openai', 'gemini', 'huggingface', 'local'), respect it.
    - If auto or unconfigured: OpenAI (if key set) -> Gemini (if key set) -> HuggingFace / Local CPU.
    """
    configured_provider = (provider or get_setting("DEFAULT_EMBEDDING_PROVIDER", "openai")).lower().strip()
    
    openai_key = get_api_key("openai")
    gemini_key = get_api_key("gemini")

    if configured_provider == "openai":
        if openai_key:
            from langchain_openai import OpenAIEmbeddings
            model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
            return OpenAIEmbeddings(openai_api_key=openai_key, model=model_name)
        elif gemini_key:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "models/embedding-001")
            return GoogleGenerativeAIEmbeddings(google_api_key=gemini_key, model=model_name)

    elif configured_provider == "gemini":
        if gemini_key:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "models/embedding-001")
            return GoogleGenerativeAIEmbeddings(google_api_key=gemini_key, model=model_name)
        elif openai_key:
            from langchain_openai import OpenAIEmbeddings
            model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
            return OpenAIEmbeddings(openai_api_key=openai_key, model=model_name)

    elif configured_provider in ("huggingface", "local"):
        try:
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
            except ImportError:
                from langchain_community.embeddings import HuggingFaceEmbeddings
            model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            return HuggingFaceEmbeddings(model_name=model_name)
        except Exception:
            return LightweightLocalEmbeddings()

    # Fallback auto-detection if preferred provider key is missing
    if openai_key:
        from langchain_openai import OpenAIEmbeddings
        model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
        return OpenAIEmbeddings(openai_api_key=openai_key, model=model_name)
    elif gemini_key:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "models/embedding-001")
        return GoogleGenerativeAIEmbeddings(google_api_key=gemini_key, model=model_name)

    try:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        model_name = model or "sentence-transformers/all-MiniLM-L6-v2"
        return HuggingFaceEmbeddings(model_name=model_name)
    except Exception:
        return LightweightLocalEmbeddings()


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    streaming: bool = True
):
    """
    Returns the appropriate LangChain Chat model instance based on configuration.
    """
    provider = (provider or get_setting("DEFAULT_LLM_PROVIDER", "openai")).lower().strip()
    temp = temperature if temperature is not None else float(get_setting("TEMPERATURE", 0.7))

    if provider == "openai":
        api_key = get_api_key("openai")
        if not api_key:
            raise ValueError("OpenAI API Key is missing. Please configure it in Settings or .env.")
        from langchain_openai import ChatOpenAI
        model_name = model or get_setting("DEFAULT_LLM_MODEL", "gpt-4o-mini")
        if not model_name or any(p in model_name.lower() for p in ("claude", "gemini", "llama", "qwen")):
            model_name = "gpt-4o-mini"
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=temp,
            streaming=streaming,
            default_headers={"Accept-Encoding": "gzip, deflate"}
        )

    elif provider == "gemini":
        api_key = get_api_key("gemini")
        if not api_key:
            raise ValueError("Gemini API Key is missing. Please configure it in Settings or .env.")
        from langchain_google_genai import ChatGoogleGenerativeAI
        model_name = model or get_setting("DEFAULT_LLM_MODEL", "gemini-1.5-flash")
        if not model_name or any(p in model_name.lower() for p in ("gpt-", "claude", "llama", "qwen")):
            model_name = "gemini-1.5-flash"
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temp,
            streaming=streaming
        )

    elif provider == "anthropic":
        api_key = get_api_key("anthropic")
        if not api_key:
            raise ValueError("Anthropic API Key is missing. Please configure it in Settings or .env.")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError(
                "Package 'langchain-anthropic' is not installed. Please install it using: pip install langchain-anthropic"
            )
        model_name = model or get_setting("DEFAULT_LLM_MODEL", "claude-3-5-sonnet-20240620")
        if not model_name or any(p in model_name.lower() for p in ("gpt-", "gemini", "llama", "qwen")):
            model_name = "claude-3-5-sonnet-20240620"
        return ChatAnthropic(
            model=model_name,
            api_key=api_key,
            temperature=temp,
            streaming=streaming
        )

    elif provider == "groq":
        api_key = get_api_key("groq")
        if not api_key:
            raise ValueError("Groq API Key is missing. Please configure it in Settings or .env.")
        from langchain_openai import ChatOpenAI
        
        configured_model = model or get_setting("DEFAULT_LLM_MODEL", "llama-3.3-70b-versatile")
        preferred_models = [
            configured_model,
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "allam-2-7b"
        ]

        active_model = configured_model
        try:
            import httpx
            with httpx.Client(timeout=3.0) as client:
                r = client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if r.status_code == 200:
                    available_ids = {
                        m["id"] for m in r.json().get("data", [])
                        if not m["id"].startswith("whisper")
                        and not m["id"].startswith("canopylabs")
                        and "guard" not in m["id"].lower()
                    }
                    if configured_model not in available_ids:
                        for cand in preferred_models:
                            if cand in available_ids:
                                active_model = cand
                                break
                        if active_model not in available_ids and available_ids:
                            # Prefer known stable chat models
                            active_model = next((x for x in available_ids if "llama" in x or "oss" in x or "qwen" in x), next(iter(available_ids)))
        except Exception:
            if not active_model or any(p in active_model.lower() for p in ("gpt-", "gemini", "claude")):
                active_model = "llama-3.3-70b-versatile"

        return ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
            model=active_model,
            temperature=temp,
            streaming=streaming,
            default_headers={"Accept-Encoding": "gzip, deflate"}
        )

    else:
        raise ValueError(f"Unsupported LLM provider: '{provider}'. Supported: openai, gemini, anthropic, groq")


async def test_connection(provider: str, api_key: str) -> Tuple[bool, str]:
    """Tests if the given API key is valid for the specified provider."""
    provider = provider.lower().strip()
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                api_key=api_key,
                model="gpt-4o-mini",
                max_tokens=5,
                default_headers={"Accept-Encoding": "gzip, deflate"}
            )
            await llm.ainvoke("Ping")
            return True, "OpenAI API Key verified successfully!"

        elif provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(google_api_key=api_key, model="gemini-1.5-flash", max_output_tokens=5)
            await llm.ainvoke("Ping")
            return True, "Gemini API Key verified successfully!"

        elif provider == "anthropic":
            try:
                from langchain_anthropic import ChatAnthropic
            except ImportError:
                return False, "Package 'langchain-anthropic' is not installed. Run: pip install langchain-anthropic"
            llm = ChatAnthropic(api_key=api_key, model="claude-3-haiku-20240307", max_tokens=5)
            await llm.ainvoke("Ping")
            return True, "Anthropic API Key verified successfully!"

        elif provider == "groq":
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if r.status_code == 200:
                    return True, "Groq API Key verified successfully!"
                else:
                    try:
                        err_detail = r.json().get("error", {}).get("message", r.text)
                    except Exception:
                        err_detail = r.text
                    return False, f"Groq verification failed: {err_detail}"

        else:
            return False, f"Unknown provider: {provider}"
    except Exception as e:
        return False, f"Verification failed: {str(e)}"
