import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load .env if present in root or workspace
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))

# Directory structure
CHROMA_DIR = DATA_DIR / "chroma"
UPLOADS_DIR = DATA_DIR / "uploads"
CONFIG_DIR = DATA_DIR / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

for d in [DATA_DIR, CHROMA_DIR, UPLOADS_DIR, CONFIG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def _load_stored_settings() -> Dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading settings.json: {e}")
    return {}


def _save_stored_settings(data: Dict[str, Any]) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving settings.json: {e}")


def get_api_key(provider: str) -> Optional[str]:
    """
    Retrieves API key by provider (openai, gemini, anthropic, groq).
    Priority:
    1. Saved settings file (modified by user in Web UI)
    2. Environment variable
    """
    key_name = f"{provider.upper()}_API_KEY"
    stored = _load_stored_settings()
    if stored.get(key_name):
        return stored[key_name].strip()
    
    env_val = os.getenv(key_name)
    if env_val:
        return env_val.strip()
    return None


def parse_bool(val: Any, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        normalized = val.strip().lower()
        if normalized in ("false", "0", "no", "off", "f"):
            return False
        if normalized in ("true", "1", "yes", "on", "t"):
            return True
    return bool(val)


def get_setting(key: str, default: Any = None) -> Any:
    stored = _load_stored_settings()
    if key in stored and stored[key] is not None:
        return stored[key]
    val = os.getenv(key)
    if val is not None:
        return val
    return default


def save_settings(new_settings: Dict[str, Any]) -> Dict[str, Any]:
    current = _load_stored_settings()
    for k, v in new_settings.items():
        if v is not None:
            # If the user passed a masked string like '••••••••', don't overwrite
            if isinstance(v, str) and (v.startswith("•••") or v.startswith("****")):
                continue
            current[k] = v.strip() if isinstance(v, str) else v
    _save_stored_settings(current)
    return get_public_settings()


def mask_key(key: Optional[str]) -> str:
    if not key or len(key.strip()) == 0:
        return ""
    stripped = key.strip()
    if len(stripped) <= 8:
        return "••••••••"
    return f"••••••••{stripped[-4:]}"


def get_public_settings() -> Dict[str, Any]:
    """Returns settings suitable for frontend display (API keys masked)."""
    stored = _load_stored_settings()
    
    openai_key = get_api_key("openai")
    gemini_key = get_api_key("gemini")
    anthropic_key = get_api_key("anthropic")
    groq_key = get_api_key("groq")

    def _safe_int(val: Any, default: int) -> int:
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def _safe_float(val: Any, default: float) -> float:
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    chunk_size = _safe_int(stored.get("CHUNK_SIZE", os.getenv("CHUNK_SIZE")), 1000)
    chunk_overlap = _safe_int(stored.get("CHUNK_OVERLAP", os.getenv("CHUNK_OVERLAP")), 200)
    temperature = _safe_float(stored.get("TEMPERATURE", os.getenv("TEMPERATURE")), 0.7)

    raw_guardrails = stored.get("STRICT_GUARDRAILS")
    if raw_guardrails is None:
        raw_guardrails = os.getenv("STRICT_GUARDRAILS", True)
    strict_guardrails = parse_bool(raw_guardrails, default=True)

    return {
        "keys_configured": {
            "openai": bool(openai_key),
            "gemini": bool(gemini_key),
            "anthropic": bool(anthropic_key),
            "groq": bool(groq_key),
        },
        "masked_keys": {
            "openai": mask_key(openai_key),
            "gemini": mask_key(gemini_key),
            "anthropic": mask_key(anthropic_key),
            "groq": mask_key(groq_key),
        },
        "default_llm_provider": stored.get("DEFAULT_LLM_PROVIDER") or os.getenv("DEFAULT_LLM_PROVIDER", "openai"),
        "default_llm_model": stored.get("DEFAULT_LLM_MODEL") or os.getenv("DEFAULT_LLM_MODEL", "gpt-4o-mini"),
        "default_embedding_provider": stored.get("DEFAULT_EMBEDDING_PROVIDER") or os.getenv("DEFAULT_EMBEDDING_PROVIDER", "openai"),
        "default_embedding_model": stored.get("DEFAULT_EMBEDDING_MODEL") or os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small"),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "temperature": temperature,
        "strict_guardrails": strict_guardrails,
    }
