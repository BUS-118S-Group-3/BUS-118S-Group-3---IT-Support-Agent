"""Centralized configuration. All paths and model names live here so we never
hardcode them inside agent code."""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def _bool(env: str, default: bool) -> bool:
    raw = os.getenv(env)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    chroma_dir: Path = Path(os.getenv("CHROMA_DIR", ROOT / "chroma_store"))
    kb_dir: Path = Path(os.getenv("KB_DIR", ROOT / "knowledge_base"))
    data_dir: Path = Path(os.getenv("DATA_DIR", ROOT / "data"))
    audit_log_path: Path = Path(os.getenv("AUDIT_LOG_PATH", ROOT / "data" / "audit_log.jsonl"))

    collection_name: str = "it_policy_kb"

    auto_approve_low_risk: bool = _bool("AUTO_APPROVE_LOW_RISK", True)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Retrieval
    top_k: int = 4
    chunk_size: int = 800
    chunk_overlap: int = 100


settings = Settings()


def require_openai_key() -> str:
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and set your key."
        )
    return settings.openai_api_key
