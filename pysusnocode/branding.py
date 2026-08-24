"""Identidade visual: logo e assinatura da Kraemer Academy."""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
LOGO = ASSETS / "kraemer_k.png"

SITE = "https://kraemeracademy.net"
ASSINATURA = "um produto Kraemer Academy"


def logo_pixmap(altura: int, cor: str | None = None, opacidade: float = 1.0):
    """Devolve o logo na altura pedida.

    `cor` repinta o desenho mantendo a transparência (para o logo aparecer
    tanto no tema claro quanto no escuro) e `opacidade` permite usá-lo como
    marca d'água discreta.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap

    if not LOGO.exists():
        return QPixmap()

    original = QPixmap(str(LOGO))
    if original.isNull():
        return QPixmap()

    escalado = original.scaledToHeight(altura, Qt.SmoothTransformation)

    if cor is None and opacidade >= 1.0:
        return escalado

    resultado = QPixmap(escalado.size())
    resultado.fill(Qt.transparent)
    pintor = QPainter(resultado)
    pintor.setOpacity(max(0.0, min(1.0, opacidade)))
    pintor.drawPixmap(0, 0, escalado)
    if cor:
        pintor.setCompositionMode(QPainter.CompositionMode_SourceIn)
        pintor.fillRect(resultado.rect(), QColor(cor))
    pintor.end()
    return resultado


def assinatura_html(cor_texto: str, cor_link: str, tamanho_px: int = 11) -> str:
    """Frase da assinatura com o link para o site."""
    return (
        f"<span style='font-size:{tamanho_px}px;color:{cor_texto};'>"
        f"{ASSINATURA} · "
        f"<a href='{SITE}' style='color:{cor_link};text-decoration:none;'>"
        "kraemeracademy.net</a></span>"
    )
