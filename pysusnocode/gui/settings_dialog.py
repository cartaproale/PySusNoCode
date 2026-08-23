"""Janela de configurações do PySusNoCode."""

from __future__ import annotations

import subprocess

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..config import Config, find_claude_cli


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Configurações — PySusNoCode")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # --- conta claude.ai / CLI -------------------------------------
        cli = find_claude_cli(config["cli_path"])
        cli_status = f"✅ encontrado em {cli}" if cli else "❌ não encontrado"
        form.addRow(QLabel("<b>Conexão pela conta claude.ai (Claude Code)</b>"))
        form.addRow("Claude Code:", QLabel(cli_status))

        cli_row = QHBoxLayout()
        self.cli_path_edit = QLineEdit(config["cli_path"])
        self.cli_path_edit.setPlaceholderText("Detectar automaticamente")
        cli_row.addWidget(self.cli_path_edit)
        browse_btn = QPushButton("Procurar…")
        browse_btn.clicked.connect(self._browse_cli)
        cli_row.addWidget(browse_btn)
        form.addRow("Caminho do claude.exe:", cli_row)

        install_btn = QPushButton("⬇ Instalar Claude Code")
        install_btn.setToolTip(
            "Abre um PowerShell e roda o instalador oficial: irm https://claude.ai/install.ps1 | iex"
        )
        install_btn.clicked.connect(self._install_cli)
        form.addRow("", install_btn)

        # --- API Anthropic ---------------------------------------------
        form.addRow(QLabel("<b>Conexão pela API da Anthropic (alternativa)</b>"))
        self.api_key_edit = QLineEdit(config["api_key"])
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("sk-ant-…  (console.anthropic.com)")
        form.addRow("Chave da Anthropic:", self.api_key_edit)

        # --- API OpenAI ------------------------------------------------
        form.addRow(QLabel("<b>Conexão pela API da OpenAI / GPT (alternativa)</b>"))
        self.openai_key_edit = QLineEdit(config["openai_api_key"])
        self.openai_key_edit.setEchoMode(QLineEdit.Password)
        self.openai_key_edit.setPlaceholderText("sk-…  (platform.openai.com/api-keys)")
        form.addRow("Chave da OpenAI:", self.openai_key_edit)

        self.openai_model_edit = QLineEdit(config["openai_custom_model"])
        self.openai_model_edit.setPlaceholderText(
            "opcional — ex.: gpt-5.6-terra (deixe vazio para usar a lista da barra)"
        )
        self.openai_model_edit.setToolTip(
            "Se a OpenAI lançar um modelo novo que ainda não está na lista do "
            "aplicativo, digite aqui o identificador dele."
        )
        form.addRow("Modelo GPT personalizado:", self.openai_model_edit)

        note = QLabel(
            "As chaves ficam salvas apenas no seu perfil do Windows "
            "(%APPDATA%\\PySusNoCode) e são enviadas somente ao serviço "
            "correspondente. Para escolher qual usar, mude “Conexão” na barra "
            "superior."
        )
        note.setWordWrap(True)
        form.addRow("", note)

        # --- comportamento --------------------------------------------
        form.addRow(QLabel("<b>Comportamento</b>"))
        self.autotest_check = QCheckBox(
            "Testar automaticamente cada célula criada e corrigir erros sozinho"
        )
        self.autotest_check.setChecked(bool(config["autotest"]))
        form.addRow(self.autotest_check)

        self.attempts_spin = QSpinBox()
        self.attempts_spin.setRange(1, 6)
        self.attempts_spin.setValue(int(config["max_fix_attempts"]))
        form.addRow("Tentativas de correção automática:", self.attempts_spin)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(30, 3600)
        self.timeout_spin.setSingleStep(30)
        self.timeout_spin.setValue(int(config["cell_timeout"]))
        self.timeout_spin.setSuffix(" s")
        form.addRow("Tempo limite por célula:", self.timeout_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _browse_cli(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Localizar claude.exe", "", "Executável (claude.exe)"
        )
        if path:
            self.cli_path_edit.setText(path)

    def _install_cli(self) -> None:
        answer = QMessageBox.question(
            self,
            "Instalar Claude Code",
            "Vou abrir uma janela do PowerShell executando o instalador oficial do "
            "Claude Code (claude.ai). Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoExit",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "irm https://claude.ai/install.ps1 | iex",
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )

    def _save(self) -> None:
        self.config["cli_path"] = self.cli_path_edit.text().strip()
        self.config["api_key"] = self.api_key_edit.text().strip()
        self.config["openai_api_key"] = self.openai_key_edit.text().strip()
        self.config["openai_custom_model"] = self.openai_model_edit.text().strip()
        self.config["autotest"] = self.autotest_check.isChecked()
        self.config["max_fix_attempts"] = self.attempts_spin.value()
        self.config["cell_timeout"] = self.timeout_spin.value()
        self.config.save()
        self.accept()
