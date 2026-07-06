"""
Unified configuration for tag-memory.

Priority (highest first):
  1. Explicit constructor keyword argument
  2. System environment variable (TAG_MEMORY_*)
  3. Local .env file (in project root or cwd)
  4. Hard-coded default

All environment variables use the TAG_MEMORY_ prefix to avoid collisions
with other projects on the same machine.

Example .env file:
    TAG_MEMORY_MYSQL_HOST=localhost
    TAG_MEMORY_MYSQL_PASSWORD=secret
    TAG_MEMORY_LLM_API_KEY=sk-xxx
    TAG_MEMORY_LLM_MODEL=gpt-4o
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv as _load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False
    _load_dotenv = None  # type: ignore[assignment]

# ── Environment variable prefixes ──────────────────────────
_MYSQL_PREFIX = "TAG_MEMORY_MYSQL_"
_LLM_PREFIX = "TAG_MEMORY_LLM_"


def _env(key: str, default: str = "") -> str:
    """Read an env var with TAG_MEMORY prefix, fall back to default."""
    return os.getenv(f"{key}", default)


# ── Auto-load .env on import ───────────────────────────────
_LOADED = False


def _auto_load_dotenv() -> None:
    """Load .env once on first access, searching cwd → project root."""
    global _LOADED
    if _LOADED or not _HAS_DOTENV:
        return
    _LOADED = True
    search_dir = os.getcwd()
    for _ in range(5):
        env_path = os.path.join(search_dir, ".env")
        if os.path.isfile(env_path):
            _load_dotenv(env_path)  # type: ignore[misc]
            return
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            break
        search_dir = parent


# ── Config dataclass ───────────────────────────────────────


@dataclass
class MySQLConfig:
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "tag_memory"

    @classmethod
    def from_env(cls) -> "MySQLConfig":
        _auto_load_dotenv()
        return cls(
            host=_env(f"{_MYSQL_PREFIX}HOST", "localhost"),
            port=int(_env(f"{_MYSQL_PREFIX}PORT", "3306")),
            user=_env(f"{_MYSQL_PREFIX}USER", "root"),
            password=_env(f"{_MYSQL_PREFIX}PASSWORD", ""),
            database=_env(f"{_MYSQL_PREFIX}DATABASE", "tag_memory"),
        )


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        _auto_load_dotenv()
        return cls(
            api_key=_env(f"{_LLM_PREFIX}API_KEY", ""),
            base_url=_env(f"{_LLM_PREFIX}BASE_URL", "https://api.openai.com/v1"),
            model=_env(f"{_LLM_PREFIX}MODEL", "gpt-4o-mini"),
        )


@dataclass
class Config:
    """Top-level config for tag-memory."""

    mysql: MySQLConfig = field(default_factory=MySQLConfig.from_env)
    llm: LLMConfig = field(default_factory=LLMConfig.from_env)

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            mysql=MySQLConfig.from_env(),
            llm=LLMConfig.from_env(),
        )

    def to_mysql_kwargs(self) -> dict:
        return {
            "host": self.mysql.host,
            "port": self.mysql.port,
            "user": self.mysql.user,
            "password": self.mysql.password,
            "database": self.mysql.database,
        }
