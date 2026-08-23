"""Painel do notebook: lista de células com botões de ação."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..nb import Cell, Notebook
from ..theme import LIGHT
from .cell_widget import CellWidget


class NotebookPanel(QWidget):
    run_cell_requested = Signal(object)      # CellWidget
    fix_cell_requested = Signal(object)      # CellWidget
    run_all_requested = Signal()
    restart_kernel_requested = Signal()
    cell_deleted = Signal(object)            # Cell
    save_requested = Signal()
    open_requested = Signal()
    changed = Signal()                       # qualquer alteração no notebook

    def __init__(self, notebook: Notebook, parent=None):
        super().__init__(parent)
        self.notebook = notebook
        self.widgets: list[CellWidget] = []
        self.tokens = LIGHT
        self.font_px = 13

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        header = QHBoxLayout()
        self.title_label = QLabel("📓 Notebook")
        header.addWidget(self.title_label)
        header.addStretch(1)

        run_all_btn = QPushButton("▶▶ Executar tudo")
        run_all_btn.clicked.connect(self.run_all_requested.emit)
        header.addWidget(run_all_btn)

        add_btn = QPushButton("➕ Célula")
        add_btn.setToolTip("Adicionar uma célula de código vazia")
        add_btn.clicked.connect(self._add_empty_cell)
        header.addWidget(add_btn)

        open_btn = QPushButton("📂 Abrir")
        open_btn.setToolTip(
            "Abrir um notebook .ipynb salvo anteriormente (restaura também a conversa)"
        )
        open_btn.clicked.connect(self.open_requested.emit)
        header.addWidget(open_btn)

        save_btn = QPushButton("💾 Salvar")
        save_btn.setToolTip(
            "Salvar o notebook (.ipynb) com a conversa junto — abre no Colab e no Jupyter"
        )
        save_btn.clicked.connect(self.save_requested.emit)
        header.addWidget(save_btn)

        copy_btn = QPushButton("📋 Copiar tudo")
        copy_btn.setToolTip("Copiar todas as células para a área de transferência")
        copy_btn.clicked.connect(self._copy_all)
        header.addWidget(copy_btn)

        colab_btn = QPushButton("🌐 Colab")
        colab_btn.setToolTip("Abrir o Google Colab no navegador (faça upload do .ipynb salvo)")
        colab_btn.clicked.connect(lambda: webbrowser.open("https://colab.research.google.com/"))
        header.addWidget(colab_btn)

        restart_btn = QPushButton("🔄 Kernel")
        restart_btn.setToolTip("Reiniciar o kernel Python (limpa variáveis carregadas)")
        restart_btn.clicked.connect(self.restart_kernel_requested.emit)
        header.addWidget(restart_btn)

        layout.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.cells_layout = QVBoxLayout(self.container)
        self.cells_layout.setAlignment(Qt.AlignTop)
        self.cells_layout.setSpacing(8)
        self.empty_label = QLabel(
            "As células criadas pela IA aparecerão aqui,\nprontas para executar, editar e copiar."
        )
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.cells_layout.addWidget(self.empty_label)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, stretch=1)
        self.apply_appearance(self.tokens, self.font_px)

    # ------------------------------------------------------------------
    # Aparência (acessibilidade)
    # ------------------------------------------------------------------
    def apply_appearance(self, t: dict, font_px: int) -> None:
        self.tokens = t
        self.font_px = font_px
        self.title_label.setStyleSheet(
            f"font-weight:bold; font-size:{font_px}px; color:{t['text']};"
        )
        self.scroll.setStyleSheet(
            f"QScrollArea{{border:1px solid {t['border']};background:{t['nb_scroll_bg']};}}"
        )
        self.container.setStyleSheet(f"background:{t['nb_scroll_bg']};")
        self.empty_label.setStyleSheet(
            f"color:{t['nb_empty_fg']};padding:40px;background:transparent;"
        )
        for widget in self.widgets:
            widget.apply_appearance(t, font_px)

    # ------------------------------------------------------------------
    def add_cell(self, cell: Cell) -> CellWidget:
        self.empty_label.setVisible(False)
        widget = CellWidget(cell, self.tokens, self.font_px)
        widget.run_requested.connect(self.run_cell_requested.emit)
        widget.fix_requested.connect(self.fix_cell_requested.emit)
        widget.delete_requested.connect(self._on_delete)
        widget.edited.connect(lambda _w: self.changed.emit())
        self.widgets.append(widget)
        self.cells_layout.addWidget(widget)
        self.renumber()
        self.scroll_to_widget(widget)
        return widget

    def _add_empty_cell(self) -> None:
        cell = self.notebook.add("code", "")
        self.add_cell(cell)
        self.changed.emit()

    def _on_delete(self, widget: CellWidget) -> None:
        answer = QMessageBox.question(
            self,
            "Excluir célula",
            "Excluir esta célula do notebook?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.notebook.remove(widget.cell)
        self.widgets.remove(widget)
        widget.setParent(None)
        widget.deleteLater()
        self.cell_deleted.emit(widget.cell)
        self.changed.emit()
        self.renumber()
        if not self.widgets:
            self.empty_label.setVisible(True)

    def widget_for(self, cell: Cell) -> CellWidget | None:
        for widget in self.widgets:
            if widget.cell is cell:
                return widget
        return None

    def renumber(self) -> None:
        for i, widget in enumerate(self.widgets, start=1):
            widget.set_number(i)

    def scroll_to_widget(self, widget: CellWidget) -> None:
        QApplication.processEvents()
        self.scroll.ensureWidgetVisible(widget, 0, 40)

    def clear(self) -> None:
        for widget in self.widgets:
            widget.setParent(None)
            widget.deleteLater()
        self.widgets = []
        self.empty_label.setVisible(True)

    # ------------------------------------------------------------------
    def _copy_all(self) -> None:
        if not self.notebook.cells:
            QMessageBox.information(self, "Notebook vazio", "Ainda não há células para copiar.")
            return
        QApplication.clipboard().setText(self.notebook.as_clipboard_text())
        QMessageBox.information(
            self,
            "Copiado",
            "Todas as células foram copiadas para a área de transferência.",
        )
