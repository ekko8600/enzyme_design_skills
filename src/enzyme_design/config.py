"""Configuration for the enzyme-design literature runtime.

The project intentionally keeps configuration simple and environment-variable
focused on agent skills and shell-based workflows without a frontend.

All API keys support two modes:
1. Direct env var:    DEEPSEEK_API_KEY=sk-xxx
2. File-based:        DEEPSEEK_API_KEY_FILE=~/.secrets/deepseek.key
   The file should contain only the key value (no extra whitespace).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _read_secret(env_name: str, file_env_name: str, default_file: str | None = None) -> str | None:
    """Read a secret from env var, or fall back to reading from a local file.

    Priority: direct env var > file_env path > default_file path.
    """
    value = os.getenv(env_name)
    if value:
        return value.strip() or None

    file_path = os.getenv(file_env_name) or default_file
    if file_path:
        expanded = Path(file_path).expanduser()
        if expanded.is_file():
            content = expanded.read_text(encoding="utf-8").strip()
            if content:
                return content
    return None


def _env_path(primary: str, legacy: str, default: Path) -> Path:
    """Read a path setting while preserving legacy literature-wiki variables."""
    return Path(os.getenv(primary, os.getenv(legacy, default)))


@dataclass(frozen=True)
class Settings:
    root_dir: Path = field(default_factory=Path.cwd)
    data_dir: Path = field(default_factory=lambda: Path("data"))
    parsed_dir: Path = field(default_factory=lambda: Path("data/parsed"))
    index_path: Path = field(default_factory=lambda: Path("data/index/enzyme_design.sqlite3"))
    vault_dir: Path = field(default_factory=lambda: Path("vault"))

    # --- DeepSeek LLM ---
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    semantic_scholar_api_key: str | None = None

    # --- PDF parser: local CLI (kept for backward compatibility) ---
    pdf_parser_backend: str = "auto"
    mineru_command: str = "mineru"
    mineru_mode: str = "local"
    paddleocr_command: str = "paddleocr"

    # --- MinerU HTTP API ---
    mineru_api_url: str | None = None
    mineru_api_key: str | None = None

    # --- PaddleOCR HTTP API ---
    paddleocr_api_url: str | None = None
    paddleocr_api_key: str | None = None

    # --- Network / privacy ---
    allow_network_search: bool = True
    allow_upload_private_notes_to_llm: bool = True

    @classmethod
    def from_env(cls, root_dir: Path | None = None) -> "Settings":
        root = root_dir or _env_path("ENZYME_DESIGN_ROOT", "LITERATURE_WIKI_ROOT", Path.cwd())
        data = _env_path("ENZYME_DESIGN_DATA_DIR", "LITERATURE_WIKI_DATA_DIR", root / "data")
        vault = _env_path("ENZYME_DESIGN_VAULT_DIR", "LITERATURE_WIKI_VAULT_DIR", root / "vault")

        return cls(
            root_dir=root,
            data_dir=data,
            parsed_dir=_env_path("ENZYME_DESIGN_PARSED_DIR", "LITERATURE_WIKI_PARSED_DIR", data / "parsed"),
            index_path=_env_path("ENZYME_DESIGN_INDEX", "LITERATURE_WIKI_INDEX", data / "index" / "enzyme_design.sqlite3"),
            vault_dir=vault,

            # DeepSeek — key from env or file
            deepseek_api_key=_read_secret(
                "DEEPSEEK_API_KEY",
                "DEEPSEEK_API_KEY_FILE",
                "~/.secrets/deepseek.key",
            ),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
            semantic_scholar_api_key=_read_secret("SEMANTIC_SCHOLAR_API_KEY", "SEMANTIC_SCHOLAR_API_KEY_FILE", "~/.secrets/semanticscholar.key"),

            # Local CLI parsers
            pdf_parser_backend=os.getenv("PDF_PARSER_BACKEND", "auto"),
            mineru_command=os.getenv("MINERU_COMMAND", "mineru"),
            mineru_mode=os.getenv("MINERU_MODE", "local"),
            paddleocr_command=os.getenv("PADDLEOCR_COMMAND", "paddleocr"),

            # MinerU HTTP API
            mineru_api_url=os.getenv("MINERU_API_URL"),
            mineru_api_key=_read_secret(
                "MINERU_API_KEY",
                "MINERU_API_KEY_FILE",
                "~/.secrets/mineru.key",
            ),

            # PaddleOCR HTTP API
            paddleocr_api_url=os.getenv("PADDLEOCR_API_URL"),
            paddleocr_api_key=_read_secret(
                "PADDLEOCR_API_KEY",
                "PADDLEOCR_API_KEY_FILE",
                "~/.secrets/paddleocr.key",
            ),

            allow_network_search=_env_bool_fallback("ENZYME_DESIGN_ALLOW_NETWORK", "LITERATURE_WIKI_ALLOW_NETWORK", True),
            allow_upload_private_notes_to_llm=_env_bool_fallback(
                "ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD",
                "LITERATURE_WIKI_ALLOW_PRIVATE_UPLOAD",
                True,
            ),
        )

    def ensure_directories(self) -> None:
        """Create standard runtime directories."""
        for directory in [
            self.data_dir / "raw",
            self.parsed_dir,
            self.index_path.parent,
            self.vault_dir / "papers",
            self.vault_dir / "topics",
            self.vault_dir / "concepts",
            self.vault_dir / "research_logs",
            self.vault_dir / "archive",
            self.vault_dir / "assets",
        ]:
            directory.mkdir(parents=True, exist_ok=True)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_bool_fallback(primary: str, legacy: str, default: bool) -> bool:
    if os.getenv(primary) is not None:
        return _env_bool(primary, default)
    return _env_bool(legacy, default)
