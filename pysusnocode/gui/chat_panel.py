"""Painel de conversa (estilo chat) do PySusNoCode.

Todas as cores de texto e fundo são definidas EXPLICITAMENTE pelos tokens do
tema atual (claro/escuro) — nada herda cores do sistema, garantindo contraste
legível em qualquer configuração do Windows.
"""

from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..theme import LIGHT

_FENCE_RE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)


class _PromptInput(QPlainTextEdit):
    """Campo de texto que envia com Enter (Shift+Enter quebra linha)."""

    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
            event.modifiers() & Qt.ShiftModifier
        ):
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class ChatPanel(QWidget):
    send_requested = Signal(str)
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.t = LIGHT               # tokens do tema atual
        self.font_px = 13
        self.entries: list[tuple[str, str]] = []   # (papel, html)
        self._streaming = False
        self._stream_buffer = ""
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(150)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.title_label = QLabel("💬 Conversa")
        layout.addWidget(self.title_label)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        layout.addWidget(self.view, stretch=1)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        input_row = QHBoxLayout()
        self.input = _PromptInput()
        self.input.setPlaceholderText(
            "Descreva o que você quer analisar (ex.: casos de dengue em 2024 no seu estado)…"
        )
        self.input.setFixedHeight(72)
        self.input.submitted.connect(self._on_send_clicked)
        input_row.addWidget(self.input, stretch=1)

        buttons = QVBoxLayout()
        self.send_btn = QPushButton("Enviar ➤")
        self.send_btn.setFixedHeight(34)
        self.send_btn.setStyleSheet(
            "QPushButton{background:#2b6cb0;color:#ffffff;font-weight:bold;border-radius:4px;}"
            "QPushButton:disabled{background:#7a879b;color:#e8ecf2;}"
        )
        self.send_btn.clicked.connect(self._on_send_clicked)
        buttons.addWidget(self.send_btn)

        self.stop_btn = QPushButton("⏹ Parar")
        self.stop_btn.setFixedHeight(30)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        buttons.addWidget(self.stop_btn)
        input_row.addLayout(buttons)

        layout.addLayout(input_row)
        self.set_appearance(self.t, self.font_px)

    # ------------------------------------------------------------------
    # Aparência (acessibilidade)
    # ------------------------------------------------------------------
    def set_appearance(self, t: dict, font_px: int) -> None:
        self.t = t
        self.font_px = font_px
        self.title_label.setStyleSheet(
            f"font-weight:bold; font-size:{font_px}px; color:{t['text']};"
        )
        self.view.setStyleSheet(
            f"QTextBrowser{{background:{t['base']};border:1px solid {t['border']};}}"
        )
        self.status_label.setStyleSheet(f"color:{t['muted']}; font-style:italic;")
        self.input.setFont(QFont("Segoe UI", max(9, int(font_px * 0.75))))
        self.input.setStyleSheet(
            f"QPlainTextEdit{{background:{t['base']};color:{t['text']};"
            f"border:1px solid {t['border']};border-radius:4px;}}"
        )
        self._render()

    def _md_to_html(self, text: str) -> str:
        """Conversão levinha de markdown para HTML com cores explícitas."""
        t = self.t
        placeholders: list[str] = []

        def _fence(match: re.Match) -> str:
            code = html.escape(match.group(1).rstrip("\n"))
            placeholders.append(
                f"<pre style='background:{t['code_bg']};color:{t['code_fg']};"
                f"padding:6px;border-radius:4px;'>{code}</pre>"
            )
            return f"\x00{len(placeholders) - 1}\x00"

        text = _FENCE_RE.sub(_fence, text)
        text = html.escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(
            r"`([^`\n]+)`",
            rf"<code style='background:{t['code_bg']};color:{t['code_fg']};"
            r"padding:1px 3px;border-radius:3px;'>\1</code>",
            text,
        )
        text = re.sub(r"^#{1,4}\s*(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
        text = re.sub(r"^[-*]\s+", "&nbsp;&nbsp;• ", text, flags=re.MULTILINE)
        text = text.replace("\n", "<br>")
        for i, block in enumerate(placeholders):
            text = text.replace(f"\x00{i}\x00", block)
        return text

    # ------------------------------------------------------------------
    def _on_send_clicked(self) -> None:
        text = self.input.toPlainText().strip()
        if not text or not self.send_btn.isEnabled():
            return
        self.input.clear()
        self.send_requested.emit(text)

    def set_busy(self, busy: bool, status: str = "") -> None:
        self.send_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.status_label.setText(status)

    # ------------------------------------------------------------------
    def add_html(self, role: str, html_content: str) -> None:
        self.entries.append((role, html_content))
        self._render()

    def add_user(self, text: str) -> None:
        self.add_html("user", html.escape(text).replace("\n", "<br>"))

    def add_assistant(self, text: str) -> None:
        self.add_html("assistant", self._md_to_html(text))

    def add_app_note(self, text: str) -> None:
        self.add_html("app", html.escape(text).replace("\n", "<br>"))

    def add_error(self, text: str) -> None:
        self.add_html("error", html.escape(text).replace("\n", "<br>"))

    # --- streaming -----------------------------------------------------
    def begin_stream(self) -> None:
        self._streaming = True
        self._stream_buffer = ""
        self._render()

    def stream_chunk(self, text: str) -> None:
        if not self._streaming:
            return
        self._stream_buffer += text
        if not self._render_timer.isActive():
            self._render_timer.start()

    def end_stream(self, final_text: str | None) -> None:
        self._streaming = False
        self._stream_buffer = ""
        self._render_timer.stop()
        if final_text:
            self.add_assistant(final_text)
        else:
            self._render()

    # ------------------------------------------------------------------
    def _bubble_style(self, role: str) -> tuple[str, str, str]:
        t = self.t
        styles = {
            "user": ("Você", t["chat_user_bg"], t["chat_user_fg"]),
            "assistant": ("Claude", t["chat_assistant_bg"], t["chat_assistant_fg"]),
            "app": ("PySusNoCode", t["chat_app_bg"], t["chat_app_fg"]),
            "error": ("Erro", t["chat_error_bg"], t["chat_error_fg"]),
        }
        return styles.get(role, styles["app"])

    def _render(self) -> None:
        t = self.t
        parts = [
            f"<html><body style='font-family:Segoe UI;font-size:{self.font_px}px;"
            f"color:{t['text']};background:{t['base']};'>"
        ]
        for role, content in self.entries:
            name, bg, fg = self._bubble_style(role)
            parts.append(
                f"<div style='background:{bg};color:{fg};margin:6px 2px;padding:8px;"
                f"border-radius:6px;'><span style='font-weight:bold;'>"
                f"{name}:</span><br>{content}</div>"
            )
        if self._streaming:
            name, bg, fg = self._bubble_style("assistant")
            live = html.escape(self._stream_buffer).replace("\n", "<br>")
            parts.append(
                f"<div style='background:{bg};color:{fg};margin:6px 2px;padding:8px;"
                f"border-radius:6px;'><span style='font-weight:bold;'>"
                f"{name}:</span><br>{live}<span style='color:{t['muted']};'> ▌</span></div>"
            )
        parts.append("</body></html>")
        self.view.setHtml("".join(parts))
        scrollbar = self.view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def reset(self, welcome_html: str) -> None:
        self.entries = []
        self._streaming = False
        self._stream_buffer = ""
        self.add_html("app", welcome_html)
