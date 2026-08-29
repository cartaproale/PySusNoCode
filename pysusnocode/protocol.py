"""Interpretação das respostas do Claude: extrai células e lições do texto."""

from __future__ import annotations

import re
from dataclasses import dataclass

# O ':12' final e opcional e significa SUBSTITUA a celula 12. Sem ele, a
# celula e acrescentada ao fim, que era o unico comportamento ate a 1.8.23.
_CELL_RE = re.compile(
    r"###\s*CELULA\s*:\s*(codigo|texto)\s*(?::\s*(\d+)\s*)?###\s*\n"
    r"(.*?)\n?\s*###\s*FIM\s*###",
    re.DOTALL | re.IGNORECASE,
)
_LESSON_RE = re.compile(
    r"###\s*LICAO\s*###\s*\n?(.*?)\n?\s*###\s*FIM\s*###",
    re.DOTALL | re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n(.*)\n```\s*$", re.DOTALL)


@dataclass
class ParsedCell:
    kind: str      # "code" | "markdown"
    source: str
    # Posição (base 1) da célula a SUBSTITUIR, quando a IA endereçou uma.
    # None significa acrescentar ao fim.
    alvo: int | None = None


@dataclass
class ParsedResponse:
    chat_text: str            # texto da conversa, com as células substituídas
    cells: list[ParsedCell]
    lessons: list[str]


def _strip_fence(text: str) -> str:
    """Remove cerca de markdown caso o modelo tenha envolvido o conteúdo."""
    match = _FENCE_RE.match(text.strip())
    if match:
        return match.group(1)
    return text


def parse_response(
    text: str, numero_inicial: int = 1, verbo: str = "adicionada ao"
) -> ParsedResponse:
    """Extrai as células da resposta.

    `numero_inicial` é a posição que a primeira célula ocupará no notebook —
    sem isso a contagem reiniciaria em cada resposta e o aviso no chat não
    corresponderia à célula real.
    """
    cells: list[ParsedCell] = []

    def _cell_placeholder(match: re.Match) -> str:
        kind = "code" if match.group(1).lower() == "codigo" else "markdown"
        alvo = int(match.group(2)) if match.group(2) else None
        source = _strip_fence(match.group(3)).strip("\n")
        cells.append(ParsedCell(kind=kind, source=source, alvo=alvo))
        label = "código" if kind == "code" else "texto"
        if alvo is not None:
            # Quem endereçou a célula diz o número dela, não a posição na fila.
            return f"\n📋 *célula de {label} nº{alvo} substituída*\n"
        # Só as que serão acrescentadas ocupam posição nova no fim: uma
        # substituição não empurra a numeração das seguintes.
        acrescentadas = sum(1 for c in cells if c.alvo is None)
        numero = numero_inicial + acrescentadas - 1
        return f"\n📋 *célula de {label} nº{numero} {verbo} notebook*\n"

    remainder = _CELL_RE.sub(_cell_placeholder, text)

    lessons: list[str] = []

    def _lesson_placeholder(match: re.Match) -> str:
        lesson = " ".join(match.group(1).split())
        if lesson:
            lessons.append(lesson)
        return ""

    remainder = _LESSON_RE.sub(_lesson_placeholder, remainder)

    return ParsedResponse(
        chat_text=remainder.strip(),
        cells=cells,
        lessons=lessons,
    )
