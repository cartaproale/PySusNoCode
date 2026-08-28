r"""Registro de diagnóstico do PySusNoCode.

Guarda em %APPDATA%\PySusNoCode\diagnostico.log os erros de comunicação com
os serviços de IA, com data/hora e o identificador da requisição — o que
permite investigar depois problemas intermitentes (que somem quando se tenta
reproduzir). Nunca registra chaves de API.

Guarda também as últimas linhas em memória. Isso existe porque houve um caso em
que o aplicativo não conseguiu gravar nada na pasta de dados: a falha que
precisávamos investigar não deixou rastro nenhum, e a ausência de rastro só foi
percebida horas depois. Com a cópia em memória, a interface consegue mostrar o
histórico mesmo quando o disco não colabora.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime

from .config import APP_DIR

LOG_FILE = APP_DIR / "diagnostico.log"
MAX_BYTES = 512 * 1024
MAX_EM_MEMORIA = 200

# Últimas linhas registradas nesta execução, gravadas em disco ou não.
RECENTES: deque[str] = deque(maxlen=MAX_EM_MEMORIA)

# Por que a gravação em disco parou de funcionar, se parou. Vazio = tudo bem.
FALHA_AO_GRAVAR = ""


def registrar(evento: str, detalhe: str = "") -> None:
    """Anexa uma linha ao log de diagnóstico.

    Nunca levanta — registrar um problema não pode virar um segundo problema —
    mas também não desaparece: quando a gravação falha, o motivo fica em
    FALHA_AO_GRAVAR e a linha continua disponível em RECENTES.
    """
    global FALHA_AO_GRAVAR

    agora = datetime.now().isoformat(timespec="seconds")
    linha = f"[{agora}] {evento}"
    if detalhe:
        linha += f" | {' '.join(str(detalhe).split())[:600]}"
    RECENTES.append(linha)

    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_BYTES:
            texto = LOG_FILE.read_text(encoding="utf-8", errors="replace")
            LOG_FILE.write_text(texto[-MAX_BYTES // 2:], encoding="utf-8")
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(linha + "\n")
    except Exception as erro:  # noqa: BLE001
        FALHA_AO_GRAVAR = (
            f"Não consigo gravar o registro de diagnóstico em {LOG_FILE} "
            f"({type(erro).__name__}: {erro})."
        )
    else:
        FALHA_AO_GRAVAR = ""


def historico(limite: int = 20) -> str:
    """As últimas linhas registradas nesta execução, para exibir ao usuário."""
    linhas = list(RECENTES)[-limite:]
    return "\n".join(linhas)


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
