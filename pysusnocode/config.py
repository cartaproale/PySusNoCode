"""Configurações persistentes do PySusNoCode (salvas em %APPDATA%\\PySusNoCode)."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "PySusNoCode"
CONFIG_FILE = APP_DIR / "config.json"
LESSONS_FILE = APP_DIR / "lessons.json"
NOTEBOOKS_DIR = Path.home() / "Documents" / "PySusNoCode"

BACKEND_AGENT = "agent_sdk"   # conta claude.ai via CLI do Claude Code
BACKEND_API = "api"           # chave de API da Anthropic
BACKEND_OPENAI = "openai"     # chave de API da OpenAI (GPT)

BACKEND_LABELS = [
    (BACKEND_AGENT, "Conta claude.ai (Claude Code)"),
    (BACKEND_API, "API Anthropic (chave)"),
    (BACKEND_OPENAI, "API OpenAI / GPT (chave)"),
]

# (rótulo exibido, id do modelo)
CLAUDE_MODELS = [
    ("Claude Opus 5 (recomendado)", "claude-opus-5"),
    ("Claude Sonnet 5 (mais rápido)", "claude-sonnet-5"),
    ("Claude Haiku 4.5 (mais leve)", "claude-haiku-4-5"),
    ("Claude Fable 5 (mais capaz)", "claude-fable-5"),
    ("Padrão do Claude Code", None),
]

OPENAI_MODELS = [
    ("GPT-5.6 Terra (recomendado)", "gpt-5.6-terra"),
    ("GPT-5.6 Sol (mais capaz)", "gpt-5.6-sol"),
    ("GPT-5.6 Luna (mais econômico)", "gpt-5.6-luna"),
    ("GPT-5.5", "gpt-5.5"),
    ("GPT-5.4 mini (mais leve)", "gpt-5.4-mini"),
]

MODELS = CLAUDE_MODELS  # compatibilidade


ROTULO_PERSONALIZADO = "Personalizado: {}"


def models_for(backend: str, custom_model: str = ""):
    """Lista de modelos oferecida para cada modo de conexão.

    Quando o usuário cadastra um modelo GPT próprio nas Configurações, ele
    entra na lista como mais uma opção — visível e selecionável. Antes o
    modelo personalizado era usado em silêncio, e a barra continuava exibindo
    outro nome; quem escolhesse "GPT-5.6 Terra" recebia o personalizado sem
    ficar sabendo.
    """
    if backend != BACKEND_OPENAI:
        return CLAUDE_MODELS
    custom = (custom_model or "").strip()
    if not custom:
        return OPENAI_MODELS
    return OPENAI_MODELS + [(ROTULO_PERSONALIZADO.format(custom), custom)]


def assistant_name(backend: str) -> str:
    """Nome de quem responde no chat, conforme o serviço escolhido."""
    return "GPT" if backend == BACKEND_OPENAI else "Claude"


DEFAULTS = {
    "backend": BACKEND_AGENT,
    "model_index": 0,          # índice em CLAUDE_MODELS
    "openai_model_index": 0,   # índice em OPENAI_MODELS
    "api_key": "",             # chave da Anthropic
    "openai_api_key": "",      # chave da OpenAI
    "openai_custom_model": "", # id de modelo GPT digitado pelo usuário (opcional)
    # Marca que o modelo personalizado já foi oferecido na barra e selecionado
    # uma vez. Sem isso, toda abertura voltaria a forçá-lo, e o usuário não
    # conseguiria escolher outro da lista.
    "openai_custom_escolhido": False,
    "cli_path": "",            # vazio = detectar automaticamente
    "autotest": True,
    "max_fix_attempts": 3,
    "cell_timeout": 600,       # segundos; downloads do DATASUS podem demorar
    "check_updates": True,     # verificar versão nova a cada abertura
    "last_update_check": "",   # data da última consulta (só registro)
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


def listar_claude_clis(override: str = "") -> list[str]:
    """Todos os executáveis do Claude Code presentes, em ordem de preferência.

    A biblioteca claude-agent-sdk já traz um claude.exe embutido, e é ele que
    o SDK usa para conversar. Procuramos esse primeiro para que o botão de
    login use exatamente o mesmo programa — assim não é preciso instalar o
    Claude Code separadamente.

    Devolve a lista inteira, e não só o primeiro, porque é comum a máquina ter
    dois: o embutido e o que o próprio usuário instalou em ~/.local/bin. Se a
    criação do processo falhar com um deles, quem chama pode tentar o outro em
    vez de declarar que o Claude Code não existe.
    """
    import importlib.util
    import shutil

    achados: list[str] = []

    def acrescentar(caminho) -> None:
        if not caminho:
            return
        texto = str(caminho)
        if texto not in achados and Path(texto).exists():
            achados.append(texto)

    if override:
        acrescentar(override)

    try:
        spec = importlib.util.find_spec("claude_agent_sdk")
        if spec is not None and spec.origin:
            acrescentar(Path(spec.origin).parent / "_bundled" / "claude.exe")
    except Exception:  # noqa: BLE001
        pass

    acrescentar(Path.home() / ".local" / "bin" / "claude.exe")

    hit = shutil.which("claude.exe") or shutil.which("claude")
    if hit and hit.lower().endswith((".exe", ".com")):
        acrescentar(hit)
    return achados


def find_claude_cli(override: str = "") -> str | None:
    """O executável preferido do Claude Code, ou None se não houver nenhum."""
    achados = listar_claude_clis(override)
    return achados[0] if achados else None
