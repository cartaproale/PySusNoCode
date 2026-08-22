"""Configurações persistentes do PySusNoCode (salvas em %APPDATA%\\PySusNoCode)."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "PySusNoCode"
CONFIG_FILE = APP_DIR / "config.json"
LESSONS_FILE = APP_DIR / "lessons.json"
NOTEBOOKS_DIR = Path.home() / "Documents" / "PySusNoCode"

# (rótulo exibido, id do modelo na API, id do modelo para o CLI do Claude Code)
MODELS = [
    ("Claude Opus 5 (recomendado)", "claude-opus-5", "claude-opus-5"),
    ("Claude Sonnet 5 (mais rápido)", "claude-sonnet-5", "claude-sonnet-5"),
    ("Claude Haiku 4.5 (mais leve)", "claude-haiku-4-5", "claude-haiku-4-5"),
    ("Claude Fable 5 (mais capaz)", "claude-fable-5", "claude-fable-5"),
    ("Padrão do Claude Code", None, None),
]

BACKEND_AGENT = "agent_sdk"   # conta claude.ai via CLI do Claude Code
BACKEND_API = "api"           # chave de API da Anthropic

DEFAULTS = {
    "backend": BACKEND_AGENT,
    "model_index": 0,
    "api_key": "",
    "cli_path": "",            # vazio = detectar automaticamente
    "autotest": True,
    "max_fix_attempts": 3,
    "cell_timeout": 600,       # segundos; downloads do DATASUS podem demorar
    "theme": "claro",          # "claro" | "escuro" (acessibilidade)
    "font_size": 13,           # px, para chat e células (acessibilidade)
    "always_on_top": False,    # janela do app acima de todas as outras
}


class Config:
    def __init__(self) -> None:
        self.data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            if CONFIG_FILE.exists():
                stored = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                for key in DEFAULTS:
                    if key in stored:
                        self.data[key] = stored[key]
        except Exception:
            pass  # config corrompida: segue com os padrões

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def __getitem__(self, key: str):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value) -> None:
        self.data[key] = value


def find_claude_cli(override: str = "") -> str | None:
    """Localiza o executável nativo do Claude Code no Windows."""
    import shutil

    if override:
        p = Path(override)
        if p.exists():
            return str(p)
    candidates = [
        Path.home() / ".local" / "bin" / "claude.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    hit = shutil.which("claude.exe") or shutil.which("claude")
    if hit and hit.lower().endswith((".exe", ".com")):
        return hit
    return None
