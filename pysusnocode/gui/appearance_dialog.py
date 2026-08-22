"""Diálogo de aparência/acessibilidade: tema (claro/escuro) e tamanho da letra."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from ..config import Config


class AppearanceDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Aparência — PySusNoCode")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Claro (fundo branco, letras escuras)", "claro")
        self.theme_combo.addItem("Escuro (fundo escuro, letras claras)", "escuro")
        index = self.theme_combo.findData(config["theme"])
        self.theme_combo.setCurrentIndex(max(0, index))
        form.addRow("Tema de cores:", self.theme_combo)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(11, 24)
        self.font_spin.setValue(int(config["font_size"]))
        self.font_spin.setSuffix(" px")
        form.addRow("Tamanho da letra:", self.font_spin)

        layout.addLayout(form)

        note = QLabel(
            "As mudanças valem para o chat, as células do notebook e toda a "
            "interface, e ficam salvas para as próximas vezes."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Aplicar")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        self.config["theme"] = self.theme_combo.currentData()
        self.config["font_size"] = self.font_spin.value()
        self.config.save()
        self.accept()
