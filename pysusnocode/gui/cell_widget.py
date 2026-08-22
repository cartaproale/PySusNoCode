"""Widget visual de uma célula do notebook (código ou texto).

Cores sempre explícitas, vindas dos tokens do tema atual (claro/escuro)."""

from __future__ import annotations

import base64
import html

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QFont, QFontMetrics, QImage, QTextDocument
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from ..nb import STATUS_ERROR, STATUS_NEW, STATUS_OK, STATUS_RUNNING, Cell
from ..theme import LIGHT

_STATUS_TEXTS = {
    STATUS_NEW: ("○ não executada", "st_new"),
    STATUS_RUNNING: ("⏳ executando…", "st_run"),
    STATUS_OK: ("✅ executada com sucesso", "st_ok"),
    STATUS_ERROR: ("❌ erro", "st_err"),
}


def build_outputs_html(outputs: list[dict], doc: QTextDocument, t: dict, font_px: int) -> str:
    """Gera o HTML das saídas de uma célula (formato nbformat) e registra as
    imagens como recursos do documento. Usado na célula e no modal ampliado."""
    parts = [
        f"<html><body style='font-size:{font_px}px;"
        f"color:{t['output_fg']};background:{t['output_bg']};'>"
    ]
    counter = 0
    for out in outputs:
        otype = out.get("output_type")
        if otype == "stream":
            color = t["stream_err_fg"] if out.get("name") == "stderr" else t["output_fg"]
            text = html.escape(out.get("text", ""))
            parts.append(
                f"<pre style='color:{color};margin:2px 0;white-space:pre-wrap;'>{text}</pre>"
            )
        elif otype in ("execute_result", "display_data"):
            data = out.get("data", {})
            if "image/png" in data:
                try:
                    raw = base64.b64decode(data["image/png"])
                    image = QImage.fromData(raw, "PNG")
                    url = QUrl(f"pysusnocode://img/{counter}")
                    counter += 1
                    doc.addResource(QTextDocument.ImageResource, url, image)
                    parts.append(f"<img src='{url.toString()}'><br>")
                except Exception:  # noqa: BLE001
                    parts.append("<i>[imagem]</i>")
            elif "text/plain" in data:
                text = html.escape(str(data["text/plain"]))
                parts.append(
                    f"<pre style='color:{t['output_fg']};margin:2px 0;"
                    f"white-space:pre-wrap;'>{text}</pre>"
                )
            elif "text/html" in data:
                parts.append(str(data["text/html"]))
        elif otype == "error":
            traceback = html.escape("\n".join(out.get("traceback", [])))
            parts.append(
                f"<pre style='color:{t['output_err_fg']};background:{t['output_err_bg']};"
                f"padding:4px;margin:2px 0;white-space:pre-wrap;'>{traceback}</pre>"
            )
    parts.append("</body></html>")
    return "".join(parts)


class CellWidget(QFrame):
    run_requested = Signal(object)      # self
    fix_requested = Signal(object)
    delete_requested = Signal(object)
    edited = Signal(object)

    def __init__(self, cell: Cell, tokens: dict | None = None, font_px: int = 13, parent=None):
        super().__init__(parent)
        self.cell = cell
        self.t = tokens or LIGHT
        self.font_px = font_px

        self.setFrameShape(QFrame.StyledPanel)
        is_code = cell.kind == "code"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.title_label = QLabel()
        header.addWidget(self.title_label)

        self.status_label = QLabel()
        header.addWidget(self.status_label)
        header.addStretch(1)

        if is_code:
            self.run_btn = QPushButton("▶ Executar")
            self.run_btn.setToolTip("Executar esta célula no kernel do aplicativo")
            self.run_btn.clicked.connect(lambda: self.run_requested.emit(self))
            header.addWidget(self.run_btn)

            self.fix_btn = QPushButton("🔧 Corrigir com IA")
            self.fix_btn.setToolTip("Pedir ao Claude para corrigir o erro desta célula")
            self.fix_btn.clicked.connect(lambda: self.fix_requested.emit(self))
            self.fix_btn.setVisible(False)
            header.addWidget(self.fix_btn)

            self.zoom_btn = QPushButton("🔍 Ampliar")
            self.zoom_btn.setToolTip(
                "Ver a saída completa desta célula em uma janela grande "
                "(gráficos e tabelas inteiros)"
            )
            self.zoom_btn.clicked.connect(self.open_output_dialog)
            self.zoom_btn.setVisible(False)
            header.addWidget(self.zoom_btn)
        else:
            self.run_btn = None
            self.fix_btn = None
            self.zoom_btn = None

        copy_btn = QPushButton("📋 Copiar")
        copy_btn.setToolTip("Copiar o conteúdo desta célula (para o Colab, por exemplo)")
        copy_btn.clicked.connect(self._copy)
        header.addWidget(copy_btn)

        del_btn = QPushButton("🗑")
        del_btn.setToolTip("Excluir esta célula")
        del_btn.setFixedWidth(34)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        header.addWidget(del_btn)

        layout.addLayout(header)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(cell.source)
        self.editor.textChanged.connect(self._on_edited)
        layout.addWidget(self.editor)

        self.output_view = QTextBrowser()
        self.output_view.setVisible(False)
        self.output_view.setMaximumHeight(280)
        self.output_view.setToolTip(
            "Clique duas vezes (ou use 🔍 Ampliar) para ver a saída completa"
        )
        self.output_view.viewport().installEventFilter(self)
        layout.addWidget(self.output_view)

        self.apply_appearance(self.t, self.font_px)

    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):  # noqa: N802
        from PySide6.QtCore import QEvent

        if (
            obj is self.output_view.viewport()
            and event.type() == QEvent.MouseButtonDblClick
            and self.cell.outputs
        ):
            self.open_output_dialog()
            return True
        return super().eventFilter(obj, event)

    def open_output_dialog(self) -> None:
        if not self.cell.outputs:
            return
        from .output_dialog import OutputDialog

        dialog = OutputDialog(
            f"Saída — {self.title_label.text()}",
            self.cell.outputs,
            self.t,
            self.font_px,
            parent=self.window(),
        )
        dialog.exec()

    # ------------------------------------------------------------------
    # Aparência (acessibilidade)
    # ------------------------------------------------------------------
    def apply_appearance(self, t: dict, font_px: int) -> None:
        self.t = t
        self.font_px = font_px
        is_code = self.cell.kind == "code"
        border = t["cell_border_code"] if is_code else t["cell_border_md"]
        self.setStyleSheet(
            f"CellWidget{{border:1px solid {border};border-radius:6px;"
            f"background:{t['cell_bg']};}}"
        )
        self.title_label.setStyleSheet(
            f"font-weight:bold;color:{t['cell_title_fg']};font-size:{font_px - 1}px;"
        )
        font = QFont("Consolas", max(8, int(font_px * 0.75)))
        self.editor.setFont(font)
        self.editor.setTabStopDistance(QFontMetrics(font).horizontalAdvance(" ") * 4)
        bg = t["editor_bg_code"] if is_code else t["editor_bg_md"]
        self.editor.setStyleSheet(
            f"QPlainTextEdit{{background:{bg};color:{t['editor_fg']};"
            f"border:1px solid {t['editor_border']};border-radius:4px;}}"
        )
        self.output_view.setStyleSheet(
            f"QTextBrowser{{background:{t['output_bg']};color:{t['output_fg']};"
            f"border:1px solid {t['editor_border']};border-radius:4px;}}"
        )
        self._adjust_editor_height()
        self.refresh()

    # ------------------------------------------------------------------
    def _on_edited(self) -> None:
        self.cell.source = self.editor.toPlainText()
        self._adjust_editor_height()
        self.edited.emit(self)

    def _adjust_editor_height(self) -> None:
        lines = max(2, min(22, self.editor.document().blockCount()))
        metrics = QFontMetrics(self.editor.font())
        self.editor.setFixedHeight(int(lines * metrics.lineSpacing()) + 14)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.cell.source)

    def set_number(self, number: int) -> None:
        kind = "código" if self.cell.kind == "code" else "texto"
        self.title_label.setText(f"Célula {number} · {kind}")

    def set_source(self, source: str) -> None:
        self.cell.source = source
        self.editor.blockSignals(True)
        self.editor.setPlainText(source)
        self.editor.blockSignals(False)
        self._adjust_editor_height()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        label, color_key = _STATUS_TEXTS.get(self.cell.status, ("", "st_new"))
        if self.cell.kind != "code":
            label = ""
        self.status_label.setText(label)
        self.status_label.setStyleSheet(
            f"color:{self.t[color_key]};font-size:{self.font_px - 1}px;"
        )
        if self.fix_btn is not None:
            self.fix_btn.setVisible(self.cell.status == STATUS_ERROR)
        if self.run_btn is not None:
            self.run_btn.setEnabled(self.cell.status != STATUS_RUNNING)
        self.render_outputs()

    def render_outputs(self) -> None:
        outputs = self.cell.outputs
        has_outputs = bool(outputs) and self.cell.kind == "code"
        if self.zoom_btn is not None:
            self.zoom_btn.setVisible(has_outputs)
        if not has_outputs:
            self.output_view.setVisible(False)
            return
        html_out = build_outputs_html(
            outputs, self.output_view.document(), self.t, self.font_px - 1
        )
        self.output_view.setHtml(html_out)
        self.output_view.setVisible(True)
