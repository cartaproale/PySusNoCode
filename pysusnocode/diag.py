"""Registro de diagnóstico do PySusNoCode.

Guarda em %APPDATA%\\PySusNoCode\\diagnostico.log os erros de comunicação com
os serviços de IA, com data/hora e o identificador da requisição — o que
permite investigar depois problemas intermitentes (que somem quando se tenta
reproduzir). Nunca registra chaves de API.
"""

from __future__ import annotations

from datetime import datetime

from .config import APP_DIR

LOG_FILE = APP_DIR / "diagnostico.log"
MAX_BYTES = 512 * 1024


def registrar(evento: str, detalhe: str = "") -> None:
    """Anexa uma linha ao log de diagnóstico (silencioso em caso de falha)."""
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_BYTES:
            texto = LOG_FILE.read_text(encoding="utf-8", errors="replace")
            LOG_FILE.write_text(texto[-MAX_BYTES // 2:], encoding="utf-8")
        agora = datetime.now().isoformat(timespec="seconds")
        linha = f"[{agora}] {evento}"
        if detalhe:
            linha += f" | {' '.join(str(detalhe).split())[:600]}"
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(linha + "\n")
    except Exception:  # noqa: BLE001
        pass


def descrever_erro_api(exc) -> tuple[str, str, str]:
    """Extrai (código, mensagem, id da requisição) de um erro do SDK."""
    codigo = mensagem = req_id = ""
    corpo = getattr(exc, "body", None)
    if isinstance(corpo, dict):
        erro = corpo.get("error") or {}
        codigo = str(erro.get("code") or erro.get("type") or "")
        mensagem = str(erro.get("message") or "")
    if not mensagem:
        mensagem = str(exc)
    req_id = str(getattr(exc, "request_id", "") or "")
    if not req_id:
        headers = getattr(getattr(exc, "response", None), "headers", None)
        if headers is not None:
            req_id = str(headers.get("x-request-id", "") or "")
    return codigo, mensagem, req_id
