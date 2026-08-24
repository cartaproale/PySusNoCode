"""Registro de atalhos de teclado sem ambiguidade.

Se duas combinações iguais forem registradas no mesmo widget, o Qt considera
o atalho ambíguo e NENHUMA delas dispara. Como as constantes do Qt
(QKeySequence.ZoomIn/ZoomOut) já correspondem a Ctrl+ + e Ctrl+ − no Windows,
é fácil duplicar sem perceber — por isso o registro passa por aqui.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtGui import QKeySequence, QShortcut

# Combinações usadas para aumentar/diminuir, cobrindo os teclados brasileiros
# (onde "+" exige Shift) e o teclado numérico.
AUMENTAR = (QKeySequence.ZoomIn, "Ctrl+=", "Ctrl++", "Ctrl+Shift+=", "Ctrl+Shift++")
DIMINUIR = (QKeySequence.ZoomOut, "Ctrl+-", "Ctrl+_", "Ctrl+Shift+-")
ORIGINAL = ("Ctrl+0",)


def registrar_atalhos(
    widget, sequencias: Iterable, acao: Callable[[], None]
) -> list[QShortcut]:
    """Cria os atalhos ignorando repetições (que causariam ambiguidade)."""
    registrados: set[str] = getattr(widget, "_atalhos_registrados", set())
    widget._atalhos_registrados = registrados

    criados: list[QShortcut] = []
    for item in sequencias:
        sequencia = item if isinstance(item, QKeySequence) else QKeySequence(item)
        texto = sequencia.toString()
        if not texto or texto in registrados:
            continue
        registrados.add(texto)
        criados.append(QShortcut(sequencia, widget, activated=acao))
    return criados
