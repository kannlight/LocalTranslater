"""Runtime settings, read from environment variables (see deploy/localtranslater.env.example)."""

import os
import secrets
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def _float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value not in (None, "") else default


def _optional_bool(name: str) -> bool | None:
    value = os.environ.get(name, "").strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    return None


@dataclass
class Settings:
    ollama_url: str = field(default_factory=lambda: os.environ.get("LT_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"))
    model: str = field(default_factory=lambda: os.environ.get("LT_MODEL", "gemma4:26b"))
    # Empty password disables authentication (not recommended outside development).
    password: str = field(default_factory=lambda: os.environ.get("LT_PASSWORD", ""))
    # Key for signing session cookies. If unset, a random key is generated at startup,
    # which means everyone has to log in again after a restart.
    secret_key: str = field(default_factory=lambda: os.environ.get("LT_SECRET_KEY") or secrets.token_hex(32))
    session_days: int = field(default_factory=lambda: _int("LT_SESSION_DAYS", 30))
    # Number of translations sent to Ollama at the same time; the rest wait in line.
    # Keep this <= OLLAMA_NUM_PARALLEL on the Ollama side.
    max_concurrent: int = field(default_factory=lambda: _int("LT_MAX_CONCURRENT", 3))
    max_input_chars: int = field(default_factory=lambda: _int("LT_MAX_INPUT_CHARS", 20000))
    max_instruction_chars: int = field(default_factory=lambda: _int("LT_MAX_INSTRUCTION_CHARS", 1000))
    num_ctx: int = field(default_factory=lambda: _int("LT_NUM_CTX", 32768))
    temperature: float = field(default_factory=lambda: _float("LT_TEMPERATURE", 0.2))
    # None = don't send the "think" option to Ollama (model default).
    think: bool | None = field(default_factory=lambda: _optional_bool("LT_THINK"))
    keep_alive: str = field(default_factory=lambda: os.environ.get("LT_KEEP_ALIVE", "30m"))
    request_timeout: float = field(default_factory=lambda: _float("LT_REQUEST_TIMEOUT", 600))
