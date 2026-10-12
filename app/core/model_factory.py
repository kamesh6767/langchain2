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
    1. OpenAI (if OPENAI_API_KEY is configured)
    2. Google Gemini (if GEMINI_API_KEY is configured)
    3. HuggingFace (if sentence-transformers is installed)
    4. LightweightLocalEmbeddings (built-in offline CPU fallback, zero API keys required!)
    """
    provider = (provider or get_setting("DEFAULT_EMBEDDING_PROVIDER", "openai")).lower().strip()
    
    openai_key = get_api_key("openai")
    gemini_key = get_api_key("gemini")

    if (provider == "openai" or not gemini_key) and openai_key:
        from langchain_openai import OpenAIEmbeddings
        model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
        return OpenAIEmbeddings(openai_api_key=openai_key, model=model_name)

    elif (provider == "gemini" or not openai_key) and gemini_key:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "models/embedding-001")
        return GoogleGenerativeAIEmbeddings(google_api_key=gemini_key, model=model_name)

    # When using Groq or when neither OpenAI nor Gemini keys are supplied:
    try:
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
        from langchain_anthropic import ChatAnthropic
        model_name = model or get_setting("DEFAULT_LLM_MODEL", "claude-3-5-sonnet-20240620")
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
        
        configured_model = model or get_setting("DEFAULT_LLM_MODEL", "openai/gpt-oss-120b")
        preferred_models = [
            configured_model,
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "llama-3.3-70b-versatile",
            "qwen/qwen3.8-27b",
            "llama-3.1-8b-instant"
        ]

        active_model = configured_model
        try:
            import httpx
            r = httpx.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=3.0
            )
            if r.status_code == 200:
                available_ids = {
                    m["id"] for m in r.json().get("data", [])
                    if not m["id"].startswith("whisper") and "guard" not in m["id"]
                }
                if configured_model not in available_ids:
                    for cand in preferred_models:
                        if cand in available_ids:
                            active_model = cand
                            break
                    if active_model not in available_ids and available_ids:
                        active_model = next(iter(available_ids))
        except Exception:
            pass

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
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(api_key=api_key, model="claude-3-haiku-20240307", max_tokens=5)
            await llm.ainvoke("Ping")
            return True, "Anthropic API Key verified successfully!"

        elif provider == "groq":
            import httpx
            # Validate via models endpoint first
            r = httpx.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5.0
            )
            if r.status_code == 200:
                return True, "Groq API Key verified successfully!"
            else:
                return False, f"Groq verification failed: {r.text}"

        else:
            return False, f"Unknown provider: {provider}"
    except Exception as e:
        return False, f"Verification failed: {str(e)}"
