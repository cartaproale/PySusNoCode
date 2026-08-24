"""Interpretação das respostas do Claude: extrai células e lições do texto."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CELL_RE = re.compile(
    r"###\s*CELULA\s*:\s*(codigo|texto)\s*###\s*\n(.*?)\n?\s*###\s*FIM\s*###",
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
        source = _strip_fence(match.group(2)).strip("\n")
        cells.append(ParsedCell(kind=kind, source=source))
        label = "código" if kind == "code" else "texto"
        numero = numero_inicial + len(cells) - 1
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
