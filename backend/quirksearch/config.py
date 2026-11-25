"""Central configuration for QuirkSearch.

Every value can be overridden with an environment variable (prefix ``QS_``) so the same
code runs in development, tests and Docker without edits.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    return os.environ.get(f"QS_{name}", default)


def _env_int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(_env(name, str(default)))


@dataclass(frozen=True)
class Settings:
    # --- storage -------------------------------------------------------------------
    db_path: Path = field(default_factory=lambda: Path(_env("DB_PATH", str(BACKEND_DIR / "data" / "quirksearch.db"))))
    corpus_dir: Path = field(default_factory=lambda: Path(_env("CORPUS_DIR", str(BACKEND_DIR / "corpus"))))

    # --- HTTP / crawler (Computer Networks) -----------------------------------------
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", "http://127.0.0.1:8000"))
    user_agent: str = "QuirkSearchBot/1.0 (+educational search engine project)"
    max_depth: int = field(default_factory=lambda: _env_int("MAX_DEPTH", 3))
    max_pages: int = field(default_factory=lambda: _env_int("MAX_PAGES", 150))
    concurrency: int = field(default_factory=lambda: _env_int("CONCURRENCY", 4))
    connect_timeout: float = field(default_factory=lambda: _env_float("CONNECT_TIMEOUT", 5.0))
    read_timeout: float = field(default_factory=lambda: _env_float("READ_TIMEOUT", 10.0))
    per_host_delay: float = field(default_factory=lambda: _env_float("PER_HOST_DELAY", 0.5))
    max_page_bytes: int = 2_000_000
    max_redirects: int = 5
    max_stored_chars: int = 60_000

    # --- ranking ------------------------------------------------------------------------
    bm25_k1: float = 1.2
    bm25_b: float = 0.75

    # --- API --------------------------------------------------------------------------
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        )
    )


def get_settings() -> Settings:
    return Settings()
