from typing import Optional, Tuple
from app.config import get_api_key, get_setting


def get_embeddings(provider: Optional[str] = None, model: Optional[str] = None):
    """
    Returns the appropriate LangChain Embeddings instance based on configuration.
    Falls back gracefully if keys are missing.
    """
    provider = (provider or get_setting("DEFAULT_EMBEDDING_PROVIDER", "openai")).lower().strip()
    
    if provider == "openai":
        api_key = get_api_key("openai")
        if not api_key:
            raise ValueError("OpenAI API Key is missing. Please configure it in Settings or .env.")
        from langchain_openai import OpenAIEmbeddings
        model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
        return OpenAIEmbeddings(openai_api_key=api_key, model=model_name)

    elif provider == "gemini":
        api_key = get_api_key("gemini")
        if not api_key:
            raise ValueError("Google Gemini API Key is missing. Please configure it in Settings or .env.")
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        model_name = model or get_setting("DEFAULT_EMBEDDING_MODEL", "models/embedding-001")
        return GoogleGenerativeAIEmbeddings(google_api_key=api_key, model=model_name)

    elif provider in ("huggingface", "local"):
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            model_name = model or "sentence-transformers/all-MiniLM-L6-v2"
            return HuggingFaceEmbeddings(model_name=model_name)
        except Exception as e:
            raise RuntimeError(f"Failed to load local HuggingFace embeddings: {e}")

    else:
        raise ValueError(f"Unsupported embedding provider: '{provider}'. Supported: openai, gemini, huggingface")


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
            streaming=streaming
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
        model_name = model or get_setting("DEFAULT_LLM_MODEL", "llama-3.1-8b-instant")
        return ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
            model=model_name,
            temperature=temp,
            streaming=streaming
        )

    else:
        raise ValueError(f"Unsupported LLM provider: '{provider}'. Supported: openai, gemini, anthropic, groq")


async def test_connection(provider: str, api_key: str) -> Tuple[bool, str]:
    """Tests if the given API key is valid for the specified provider."""
    provider = provider.lower().strip()
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(api_key=api_key, model="gpt-4o-mini", max_tokens=5)
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
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, model="llama-3.1-8b-instant", max_tokens=5)
            await llm.ainvoke("Ping")
            return True, "Groq API Key verified successfully!"

        else:
            return False, f"Unknown provider: {provider}"
    except Exception as e:
        return False, f"Verification failed: {str(e)}"
