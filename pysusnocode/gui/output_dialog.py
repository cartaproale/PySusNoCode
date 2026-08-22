"""Modal de visualização ampliada da saída de uma célula."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)


class OutputDialog(QDialog):
    def __init__(self, title: str, outputs: list[dict], tokens: dict, font_px: int, parent=None):
        super().__init__(parent)
        # Import tardio para evitar dependência circular com cell_widget.
        from .cell_widget import build_outputs_html

        self.setWindowTitle(title)
        self.setSizeGripEnabled(True)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.resize(int(geo.width() * 0.85), int(geo.height() * 0.85))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.browser = QTextBrowser()
        self.browser.setStyleSheet(
            f"QTextBrowser{{background:{tokens['output_bg']};color:{tokens['output_fg']};"
            f"border:1px solid {tokens['border']};border-radius:4px;}}"
        )
        html = build_outputs_html(
            outputs, self.browser.document(), tokens, font_px + 1
        )
        self.browser.setHtml(html)
        layout.addWidget(self.browser, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_btn = QPushButton("Fechar (Esc)")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)
