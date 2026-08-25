"""Verificação de novas versões do PySusNoCode.

Consulta a última Release publicada no GitHub e compara com a versão em uso.
Nada é baixado nem instalado automaticamente: quando há novidade, o aplicativo
apenas avisa e oferece abrir a página de download no navegador.

A consulta não envia nenhum dado do usuário — é um pedido público de leitura,
e pode ser desligada nas Configurações.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date

from . import __version__

REPO = "cartaproale/PySusNoCode"
API_ULTIMA_RELEASE = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA_RELEASE = f"https://github.com/{REPO}/releases/latest"
DOWNLOAD_DIRETO = (
    f"https://github.com/{REPO}/releases/latest/download/PySusNoCode-Setup.exe"
)
TEMPO_LIMITE = 8  # segundos


@dataclass
class Atualizacao:
    versao: str
    notas: str
    pagina: str = PAGINA_RELEASE
    download: str = DOWNLOAD_DIRETO


def numero_versao(texto: str) -> tuple[int, ...]:
    """'v1.4.1' → (1, 4, 1). Partes não numéricas viram 0."""
    limpo = (texto or "").strip().lstrip("vV").split("-")[0].split("+")[0]
    partes: list[int] = []
    for pedaco in limpo.split("."):
        digitos = "".join(c for c in pedaco if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes) or (0,)


def e_mais_nova(candidata: str, atual: str = __version__) -> bool:
    a, b = numero_versao(candidata), numero_versao(atual)
    tamanho = max(len(a), len(b))
    a += (0,) * (tamanho - len(a))
    b += (0,) * (tamanho - len(b))
    return a > b


def verificar() -> Atualizacao | None:
    """Devolve a atualização disponível, ou None se já estiver em dia.
    Levanta OSError quando não consegue consultar (sem internet, por exemplo)."""
    pedido = urllib.request.Request(
        API_ULTIMA_RELEASE,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"PySusNoCode/{__version__}",
        },
    )
    with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))

    tag = str(dados.get("tag_name") or "")
    if not tag or not e_mais_nova(tag):
        return None
    notas = str(dados.get("body") or "").strip()
    if len(notas) > 600:
        notas = notas[:600].rsplit(" ", 1)[0] + "…"
    return Atualizacao(versao=tag.lstrip("vV"), notas=notas)


def marca_de_hoje() -> str:
    """Data da última consulta, guardada apenas como registro.

    Até a versão 1.8.5 esta data também servia de trava: o aplicativo
    verificava uma vez por dia. Deixou de travar — agora a consulta acontece a
    cada abertura, para que uma correção importante não demore um dia inteiro
    para chegar a quem já tem o programa instalado.
    """
    return str(date.today())
