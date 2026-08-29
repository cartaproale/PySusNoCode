"""Janela de configurações do PySusNoCode."""

from __future__ import annotations

import subprocess

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
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

from ..config import OPENAI_MODELS, Config, find_claude_cli


class _TesteOpenAIWorker(QThread):
    """Testa a chave e mede a estabilidade do modelo (o acesso a alguns
    modelos da OpenAI oscila: parte das requisições volta 403)."""

    pronto = Signal(str)

    def __init__(self, api_key: str, modelo: str, tentativas: int = 3, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.modelo = modelo
        self.tentativas = tentativas

    def run(self) -> None:  # noqa: D401
        import openai

        try:
            client = openai.OpenAI(api_key=self.api_key, max_retries=0)
            ids = {m.id for m in client.models.list()}
        except openai.AuthenticationError:
            self.pronto.emit("❌ Chave inválida — confira se copiou a chave inteira.")
            return
        except Exception as exc:  # noqa: BLE001
            self.pronto.emit(f"❌ Não consegui falar com a OpenAI: {exc}")
            return

        linhas = ["✅ Chave válida."]
        faltando = [mid for _l, mid in OPENAI_MODELS if mid not in ids]
        if faltando:
            linhas.append(
                "Modelos do aplicativo que a sua conta não lista: "
                + ", ".join(faltando)
            )

        ok = 0
        ultimo_erro = ""
        for _ in range(self.tentativas):
            try:
                client.chat.completions.create(
                    model=self.modelo,
                    messages=[{"role": "user", "content": "responda: ok"}],
                )
                ok += 1
            except Exception as exc:  # noqa: BLE001
                from ..diag import descrever_erro_api

                _codigo, mensagem, _req = descrever_erro_api(exc)
                ultimo_erro = mensagem or str(exc)

        linhas.append(f"\nModelo “{self.modelo}”: {ok} de {self.tentativas} tentativas funcionaram.")
        if ok == self.tentativas:
            linhas.append("Acesso estável — pode usar normalmente. ✅")
        elif ok == 0:
            linhas.append(
                "Este modelo não está respondendo para a sua chave. Escolha outro "
                "na barra superior (o GPT-5.6 Terra costuma ser o mais estável) ou "
                "libere o modelo em platform.openai.com → Settings → Project → Limits."
            )
        else:
            linhas.append(
                "⚠ Acesso INSTÁVEL: a OpenAI aceita só parte das requisições deste "
                "modelo. O aplicativo repete a tentativa automaticamente, mas o ideal "
                "é escolher outro modelo (ex.: GPT-5.6 Terra) ou liberar este no "
                "projeto da chave (platform.openai.com → Settings → Project → Limits)."
            )
        if ultimo_erro:
            linhas.append(f"\nÚltima resposta da OpenAI: {ultimo_erro[:300]}")
        self.pronto.emit("\n".join(linhas))


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

        self.testar_btn = QPushButton("🔎 Testar conexão com a OpenAI")
        self.testar_btn.setToolTip(
            "Verifica a chave e mede se o modelo escolhido está respondendo de "
            "forma estável"
        )
        self.testar_btn.clicked.connect(self._testar_openai)
        form.addRow("", self.testar_btn)

        self.openai_model_edit = QLineEdit(config["openai_custom_model"])
        self.openai_model_edit.setPlaceholderText(
            "opcional — ex.: gpt-5-nano (aparecerá na lista “Modelo” da barra)"
        )
        self.openai_model_edit.setToolTip(
            "Se a OpenAI lançar um modelo novo que ainda não está na lista do "
            "aplicativo, digite aqui o identificador dele. Ele passa a aparecer "
            "na lista “Modelo”, na barra superior, como “Personalizado: …”, e "
            "você escolhe ali quando usá-lo. Deixe vazio para remover a opção."
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

        self.updates_check = QCheckBox(
            "Avisar quando houver uma nova versão do PySusNoCode"
        )
        self.updates_check.setToolTip(
            "Consulta a página oficial de versões no GitHub sempre que o "
            "aplicativo é aberto. Nenhum dado seu é enviado e nada é instalado "
            "automaticamente."
        )
        self.updates_check.setChecked(bool(config["check_updates"]))
        form.addRow(self.updates_check)

        self.verificar_agora_btn = QPushButton("⬇ Verificar atualizações agora")
        self.verificar_agora_btn.clicked.connect(self._verificar_agora)
        form.addRow("", self.verificar_agora_btn)

        # Fica ao lado da verificação de versão porque responde à mesma
        # pergunta, um nível abaixo: o aplicativo está em dia, mas as
        # bibliotecas e as fontes de dados que ele usa também estão?
        self.versoes_btn = QPushButton("📦 Versões e fontes de dados")
        self.versoes_btn.setToolTip(
            "Mostra a versão da PySUS e das demais bibliotecas em uso, e o que "
            "existe de mais recente; e quais sistemas de dados estão no ar."
        )
        self.versoes_btn.clicked.connect(self._abrir_versoes)
        form.addRow("", self.versoes_btn)

        # Ao lado do tempo limite por celula, porque e a mesma pergunta vista
        # do outro lado: quanto isto costuma demorar de verdade, aqui.
        self.tempos_btn = QPushButton("⏱ Quanto costuma demorar")
        self.tempos_btn.setToolTip(
            "Tempos medidos neste computador: quanto a IA leva para responder e "
            "quanto uma célula leva para executar. Fica só aqui, não é enviado."
        )
        self.tempos_btn.clicked.connect(self._abrir_tempos)
        form.addRow("", self.tempos_btn)

        # Fica junto das versoes porque responde a mesma familia de pergunta:
        # o que exatamente este programa esta usando, e sob que condicoes.
        self.licencas_btn = QPushButton("⚖ Licenças e componentes de terceiros")
        self.licencas_btn.setToolTip(
            "O PySusNoCode é software livre (MIT) e embarca bibliotecas de "
            "outros autores, algumas com licenças que pedem atribuição."
        )
        self.licencas_btn.clicked.connect(self._abrir_licencas)
        form.addRow("", self.licencas_btn)

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

    def _testar_openai(self) -> None:
        chave = self.openai_key_edit.text().strip()
        if not chave:
            QMessageBox.information(
                self,
                "Sem chave",
                "Cole primeiro a sua chave da OpenAI no campo acima.",
            )
            return
        modelo = self.openai_model_edit.text().strip()
        if not modelo:
            indice = int(self.config["openai_model_index"] or 0)
            modelo = OPENAI_MODELS[min(indice, len(OPENAI_MODELS) - 1)][1]

        self.testar_btn.setEnabled(False)
        self.testar_btn.setText("🔎 Testando… (alguns segundos)")
        self._teste = _TesteOpenAIWorker(chave, modelo, parent=self)
        self._teste.pronto.connect(self._mostrar_resultado_teste)
        self._teste.start()

    def _mostrar_resultado_teste(self, texto: str) -> None:
        self.testar_btn.setEnabled(True)
        self.testar_btn.setText("🔎 Testar conexão com a OpenAI")
        QMessageBox.information(self, "Teste de conexão — OpenAI", texto)

    def _abrir_versoes(self) -> None:
        from .versoes_dialog import VersoesDialog

        VersoesDialog(self).exec()

    def _abrir_tempos(self) -> None:
        from .. import tempos

        linhas = tempos.resumo()
        if not any(l["medicoes"] for l in linhas):
            QMessageBox.information(
                self, "Quanto costuma demorar",
                "Ainda não há medições neste computador.\n\n"
                "O aplicativo cronometra sozinho, à medida que você usa. Depois "
                "de três respostas da IA e três células executadas, ele passa a "
                "avisar na barra de espera quanto aquilo costuma levar aqui.")
            return

        partes = ["Medido neste computador, com o seu uso:\n"]
        for linha in linhas:
            if not linha["medicoes"]:
                partes.append(f"• {linha['o_que']}: ainda sem medições")
                continue
            partes.append(
                f"• {linha['o_que']}\n"
                f"     normalmente {linha['tipico']}; nas vezes lentas, "
                f"{linha['demorado']}\n"
                f"     ({linha['medicoes']} medições)")
        partes.append(
            "\nNada disso sai daqui: os tempos ficam num arquivo na pasta do "
            "aplicativo e servem só para a barra de espera saber o que dizer.")
        QMessageBox.information(self, "Quanto costuma demorar",
                                "\n".join(partes))

    def _abrir_licencas(self) -> None:
        from ..licencas import resumo, onde_estao

        texto = resumo()
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Licenças e componentes de terceiros")
        caixa.setTextFormat(Qt.PlainText)
        caixa.setText(texto)
        pasta = onde_estao()
        if pasta is not None:
            abrir = caixa.addButton("Abrir a pasta", QMessageBox.ActionRole)
        else:
            abrir = None
        caixa.addButton("Fechar", QMessageBox.RejectRole)
        caixa.exec()
        if abrir is not None and caixa.clickedButton() is abrir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(pasta)))

    def _verificar_agora(self) -> None:
        janela = self.parent()
        if janela is not None and hasattr(janela, "on_check_updates_clicked"):
            janela.on_check_updates_clicked()
        else:  # diálogo aberto sem a janela principal (testes)
            QMessageBox.information(
                self, "Verificar atualizações", "Abra o aplicativo para verificar."
            )

    def _save(self) -> None:
        self.config["check_updates"] = self.updates_check.isChecked()
        self.config["cli_path"] = self.cli_path_edit.text().strip()
        self.config["api_key"] = self.api_key_edit.text().strip()
        self.config["openai_api_key"] = self.openai_key_edit.text().strip()
        self.config["openai_custom_model"] = self.openai_model_edit.text().strip()
        self.config["autotest"] = self.autotest_check.isChecked()
        self.config["max_fix_attempts"] = self.attempts_spin.value()
        self.config["cell_timeout"] = self.timeout_spin.value()
        self.config.save()
        self.accept()
