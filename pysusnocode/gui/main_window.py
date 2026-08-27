"""Janela principal do PySusNoCode.

Orquestra o ciclo: pedido do usuário → Claude propõe células → o app executa
cada célula no kernel → em caso de erro, pede correção ao Claude (até N
tentativas) → registra a lição aprendida para as próximas sessões.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..branding import ASSINATURA, SITE, assinatura_html, logo_pixmap
from ..config import (
    BACKEND_AGENT,
    BACKEND_API,
    BACKEND_LABELS,
    BACKEND_OPENAI,
    NOTEBOOKS_DIR,
    OPENAI_MODELS,
    Config,
    assistant_name,
    find_claude_cli,
    models_for,
)
from ..kernel import NotebookKernel, erro_de_ambiente
from ..lessons import LessonStore
from ..llm import make_backend
from ..nb import STATUS_ERROR, STATUS_NEW, STATUS_OK, STATUS_RUNNING, Cell, Notebook
from ..prompts import (
    FIX_PROMPT_TEMPLATE,
    VIDEO_TUTORIAL_URL,
    WELCOME_HTML,
    build_system_prompt,
)
from ..protocol import parse_response
from ..theme import app_stylesheet, apply_app_palette, tokens as theme_tokens
from .appearance_dialog import AppearanceDialog
from .chat_panel import ChatPanel
from .flow_layout import FlowLayout
from .notebook_panel import NotebookPanel
from .settings_dialog import SettingsDialog
from .workers import CellRunWorker, KernelStartWorker, LLMWorker, UpdateCheckWorker

PHASE_IDLE = "idle"
PHASE_LLM = "llm"
PHASE_EXEC = "exec"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.lessons = LessonStore()
        self.notebook = Notebook()
        self.kernel = NotebookKernel()
        self.backend = make_backend(self.config)

        self.phase = PHASE_IDLE
        self.kernel_state = "off"          # off | starting | ready
        self.pending_queue: list[Cell] = []
        self.fixing_cell: Cell | None = None
        self.current_cell: Cell | None = None
        self.exec_notes: list[str] = []
        self.llm_worker: LLMWorker | None = None
        self.cell_worker: CellRunWorker | None = None
        self.kernel_worker: KernelStartWorker | None = None
        self.saved_path: Path | None = None
        self.dirty = False
        self.update_worker: UpdateCheckWorker | None = None
        self.pending_update = None
        # Fica verdadeiro quando o próprio aplicativo pediu para se encerrar
        # a fim de liberar os arquivos para o instalador da versão nova.
        self.encerrando_para_atualizar = False

        self._update_title()
        self.resize(1360, 840)

        barra = self._build_toolbar()

        splitter = QSplitter(Qt.Horizontal)
        self.chat = ChatPanel()
        self.chat.send_requested.connect(self.on_user_send)
        self.chat.stop_requested.connect(self.on_stop)
        splitter.addWidget(self.chat)

        self.notebook_panel = NotebookPanel(self.notebook)
        self.notebook_panel.run_cell_requested.connect(self.on_run_cell_clicked)
        self.notebook_panel.fix_cell_requested.connect(self.on_fix_cell_clicked)
        self.notebook_panel.run_all_requested.connect(self.on_run_all)
        self.notebook_panel.restart_kernel_requested.connect(self.on_restart_kernel)
        self.notebook_panel.save_requested.connect(self.on_save_notebook)
        self.notebook_panel.open_requested.connect(self.on_open_notebook)
        self.notebook_panel.examples_requested.connect(self.on_open_example)
        self.notebook_panel.changed.connect(self._mark_dirty)
        splitter.addWidget(self.notebook_panel)
        splitter.setSizes([520, 840])

        central = QWidget()
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(barra)
        col.addWidget(splitter, stretch=1)
        self.setCentralWidget(central)

        self.status_label = QLabel()
        self.statusBar().addWidget(self.status_label)

        # Assinatura da Kraemer Academy, sempre visível no rodapé.
        self.brand_logo = QLabel()
        self.brand_logo.setToolTip(f"{ASSINATURA} — {SITE}")
        self.statusBar().addPermanentWidget(self.brand_logo)
        self.brand_label = QLabel()
        self.brand_label.setOpenExternalLinks(True)
        self.brand_label.setToolTip(f"Abrir {SITE} no navegador")
        self.statusBar().addPermanentWidget(self.brand_label)

        self.login_btn.setVisible(self.config["backend"] == BACKEND_AGENT)
        self.chat.set_assistant_name(self._assistant())
        if self.config["always_on_top"]:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self._apply_appearance()
        self._configurar_atalhos_zoom()
        self.chat.reset(WELCOME_HTML)
        self._greet_connection()
        self._update_status()
        self._start_kernel()
        self._check_updates_if_due()

    # ------------------------------------------------------------------
    # Barra superior
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> QWidget:
        """Barra superior com quebra de linha: em telas estreitas os botões
        passam para a linha de baixo em vez de sumirem."""
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setObjectName("barraSuperior")
        flow = FlowLayout(self.toolbar_widget, margin=6, spacing=6)

        new_btn = QPushButton("🆕 Nova conversa")
        new_btn.setToolTip(
            "Começar uma nova conversa e um notebook em branco (Ctrl+N)"
        )
        new_btn.setShortcut(QKeySequence.New)
        new_btn.clicked.connect(self.on_new_conversation)
        flow.addWidget(new_btn)

        flow.addWidget(self._separador())

        self.model_label = QLabel("Modelo:")
        flow.addWidget(self.model_label)
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Modelo de inteligência artificial usado nas respostas")
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        flow.addWidget(self.model_combo)

        self.backend_label = QLabel("Conexão:")
        flow.addWidget(self.backend_label)
        self.backend_combo = QComboBox()
        self.backend_combo.setToolTip("Serviço de IA usado: sua conta claude.ai, ou uma chave de API")
        for backend_id, label in BACKEND_LABELS:
            self.backend_combo.addItem(label, backend_id)
        index = self.backend_combo.findData(self.config["backend"])
        self.backend_combo.setCurrentIndex(max(0, index))
        self._reload_models()
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        flow.addWidget(self.backend_combo)

        self.login_btn = QPushButton("🔑 Entrar (claude.ai)")
        self.login_btn.setToolTip(
            "Abrir o Claude Code em uma janela para fazer login na sua conta claude.ai"
        )
        self.login_btn.clicked.connect(self.on_login)
        flow.addWidget(self.login_btn)

        flow.addWidget(self._separador())

        self.autotest_check = QCheckBox("Autoteste")
        self.autotest_check.setToolTip(
            "Executar automaticamente cada célula criada pela IA e corrigir erros sozinho"
        )
        self.autotest_check.setChecked(bool(self.config["autotest"]))
        self.autotest_check.toggled.connect(self._on_autotest_toggled)
        flow.addWidget(self.autotest_check)

        self.pin_check = QCheckBox("📌 Sempre visível")
        self.pin_check.setToolTip(
            "Manter a janela do PySusNoCode acima de todas as outras janelas"
        )
        self.pin_check.setChecked(bool(self.config["always_on_top"]))
        self.pin_check.toggled.connect(self._on_pin_toggled)
        flow.addWidget(self.pin_check)

        flow.addWidget(self._separador())

        tutorial_btn = QPushButton("🎥 Tutorial")
        tutorial_btn.setToolTip(
            "Abrir o vídeo tutorial do PySusNoCode no navegador (F1)"
        )
        tutorial_btn.setShortcut(QKeySequence.HelpContents)
        tutorial_btn.clicked.connect(self.on_tutorial)
        flow.addWidget(tutorial_btn)

        appearance_btn = QPushButton("🎨 Aparência")
        appearance_btn.setToolTip(
            "Acessibilidade: escolher tema claro ou escuro e o tamanho da letra"
        )
        appearance_btn.clicked.connect(self.on_appearance)
        flow.addWidget(appearance_btn)

        settings_btn = QPushButton("⚙ Configurações")
        settings_btn.setToolTip("Chaves de API, autoteste e tempo limite (Ctrl+,)")
        settings_btn.setShortcut(QKeySequence("Ctrl+,"))
        settings_btn.clicked.connect(self.on_settings)
        flow.addWidget(settings_btn)

        # Aparece somente quando existe versão nova publicada.
        self.update_btn = QPushButton("⬇ Atualização disponível")
        self.update_btn.setObjectName("botaoAtualizar")
        self.update_btn.clicked.connect(self.on_update_clicked)
        self.update_btn.hide()
        flow.addWidget(self.update_btn)

        return self.toolbar_widget

    @staticmethod
    def _separador() -> QFrame:
        linha = QFrame()
        # objectName próprio: sem ele, uma regra "QFrame{...}" no estilo da
        # barra atingiria também QLabel e a lista do QComboBox (ambos herdam
        # de QFrame) e apagaria o texto deles.
        linha.setObjectName("separadorBarra")
        linha.setFrameShape(QFrame.VLine)
        linha.setFixedWidth(2)
        linha.setMinimumHeight(24)
        return linha

    # ------------------------------------------------------------------
    # Estado / status
    # ------------------------------------------------------------------
    def _greet_connection(self) -> None:
        if self.config["backend"] == BACKEND_OPENAI:
            if not (self.config["openai_api_key"] or "").strip():
                self.chat.add_app_note(
                    "⚠ Conexão pela OpenAI (GPT) selecionada, mas ainda sem chave. "
                    "Abra ⚙ Configurações e cole sua chave da OpenAI."
                )
            return
        if self.config["backend"] == BACKEND_API:
            if not (self.config["api_key"] or "").strip():
                self.chat.add_app_note(
                    "⚠ Conexão pela API da Anthropic selecionada, mas ainda sem "
                    "chave. Abra ⚙ Configurações e cole sua chave."
                )
            return
        if self.config["backend"] == BACKEND_AGENT:
            cli = find_claude_cli(self.config["cli_path"])
            if cli:
                self.chat.add_app_note(
                    "Conexão: Claude Code encontrado — usarei a sua conta claude.ai. "
                    "Se aparecer erro de login, clique em “🔑 Entrar (claude.ai)”."
                )
            else:
                self.chat.add_app_note(
                    "⚠ O Claude Code não foi encontrado neste computador. Abra as "
                    "Configurações e use “Instalar Claude Code”, ou mude a Conexão "
                    "para “API Anthropic (chave)”."
                )

    def _update_status(self) -> None:
        kernel_txt = {
            "off": "kernel desligado",
            "starting": "iniciando kernel Python…",
            "ready": "kernel Python pronto",
        }[self.kernel_state]
        backend_txt = {
            BACKEND_AGENT: "conta claude.ai",
            BACKEND_API: "API Anthropic",
            BACKEND_OPENAI: "API OpenAI (GPT)",
        }.get(self.config["backend"], "?")
        self.status_label.setText(
            f"  {kernel_txt}  ·  conexão: {backend_txt}  ·  "
            f"lições aprendidas: {self.lessons.count()}"
        )

    def _set_phase(self, phase: str, status: str = "") -> None:
        self.phase = phase
        self.chat.set_busy(phase != PHASE_IDLE, status)
        self._update_status()

    def _assistant(self) -> str:
        """Nome de quem responde no chat, conforme a conexão escolhida."""
        return assistant_name(self.config["backend"])

    def _current_model(self) -> str | None:
        """Identificador do modelo escolhido na barra.

        Lê o dado guardado no próprio item, e não a posição numa lista
        recalculada: com o modelo personalizado a lista tem tamanho variável,
        e reconstruí-la aqui era mais uma chance de o rótulo exibido e o
        modelo usado se separarem.
        """
        index = self.model_combo.currentIndex()
        if index < 0:
            return None
        return self.model_combo.itemData(index)

    def _system_prompt(self) -> str:
        return build_system_prompt(self.lessons.for_prompt())

    # ------------------------------------------------------------------
    # Ações da barra
    # ------------------------------------------------------------------
    def _model_key(self) -> str:
        return (
            "openai_model_index"
            if self.config["backend"] == BACKEND_OPENAI
            else "model_index"
        )

    def _reload_models(self) -> None:
        """Repovoa a lista de modelos conforme o modo de conexão atual.

        Se houver um modelo GPT personalizado nas Configurações, ele entra na
        lista como última opção. Na primeira vez que isso acontece, deixamos
        ele já selecionado: quem cadastrou um modelo próprio quer usá-lo, e
        até a 1.8.8 era isso que acontecia (só que sem aparecer na barra).
        """
        custom = (self.config["openai_custom_model"] or "").strip()
        models = models_for(self.config["backend"], custom)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for label, model_id in models:
            self.model_combo.addItem(label, model_id)

        saved = int(self.config[self._model_key()] or 0)
        if (
            custom
            and self.config["backend"] == BACKEND_OPENAI
            and not self.config["openai_custom_escolhido"]
        ):
            saved = len(models) - 1          # o personalizado é o último
            self.config[self._model_key()] = saved
            self.config["openai_custom_escolhido"] = True
            self.config.save()

        self.model_combo.setCurrentIndex(min(max(0, saved), len(models) - 1))
        self.model_combo.blockSignals(False)

    def _on_model_changed(self, index: int) -> None:
        if index < 0:
            return
        self.config[self._model_key()] = index
        self.config.save()

    def _on_backend_changed(self, index: int) -> None:
        self.config["backend"] = self.backend_combo.itemData(index) or BACKEND_AGENT
        self.config.save()
        self.backend = make_backend(self.config)
        self._reload_models()
        self.login_btn.setVisible(self.config["backend"] == BACKEND_AGENT)
        self.chat.set_assistant_name(self._assistant())
        nome = {
            BACKEND_AGENT: "sua conta claude.ai",
            BACKEND_API: "a API da Anthropic",
            BACKEND_OPENAI: "a API da OpenAI (GPT)",
        }[self.config["backend"]]
        aviso = ""
        if self.config["backend"] == BACKEND_OPENAI and not (
            self.config["openai_api_key"] or ""
        ).strip():
            aviso = (
                " ⚠ Antes de enviar um pedido, informe sua chave da OpenAI em "
                "⚙ Configurações."
            )
        elif self.config["backend"] == BACKEND_API and not (
            self.config["api_key"] or ""
        ).strip():
            aviso = (
                " ⚠ Antes de enviar um pedido, informe sua chave da Anthropic em "
                "⚙ Configurações."
            )
        self.chat.add_app_note(
            f"Conexão alterada para {nome}. A conversa recomeça do zero "
            f"(o notebook continua intacto).{aviso}"
        )
        self._update_status()

    def _on_autotest_toggled(self, checked: bool) -> None:
        self.config["autotest"] = checked
        self.config.save()

    def _on_pin_toggled(self, checked: bool) -> None:
        self.config["always_on_top"] = checked
        self.config.save()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        self.show()  # mudar a flag recria a janela nativa; é preciso reexibir

    def on_login(self) -> None:
        cli = find_claude_cli(self.config["cli_path"])
        if not cli:
            QMessageBox.warning(
                self,
                "Claude Code não encontrado",
                "Não encontrei o Claude Code neste computador.\n"
                "Abra as Configurações e clique em “Instalar Claude Code”.",
            )
            return
        subprocess.Popen([cli, "/login"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.chat.add_app_note(
            "Abri o Claude Code em uma nova janela. Complete o login na sua conta "
            "claude.ai por lá (o navegador será aberto). Se a tela de login não "
            "aparecer sozinha, digite /login e pressione Enter nessa janela. "
            "Depois volte aqui e faça seu pedido normalmente."
        )

    # ------------------------------------------------------------------
    # Verificação de novas versões
    # ------------------------------------------------------------------
    def _check_updates_if_due(self) -> None:
        """Consulta a última versão publicada a cada abertura do aplicativo.

        A consulta roda em segundo plano e não atrasa nada: se a rede estiver
        bloqueada — como em unidades de saúde e prefeituras — ela falha em
        silêncio. A verificação diária de antes deixava o usuário até um dia
        inteiro sem saber de uma correção importante; como o aplicativo é
        aberto poucas vezes ao dia, verificar sempre custa uma requisição.
        Pode ser desligada nas Configurações.
        """
        if not self.config["check_updates"]:
            return
        self._start_update_check(manual=False)

    def _start_update_check(self, manual: bool) -> None:
        from ..updates import marca_de_hoje

        self.config["last_update_check"] = marca_de_hoje()
        self.config.save()
        worker = UpdateCheckWorker(self)
        worker.resultado.connect(
            lambda atualizacao: self._on_update_result(atualizacao, manual)
        )
        worker.falhou.connect(lambda erro: self._on_update_failed(erro, manual))
        self.update_worker = worker
        worker.start()

    def _on_update_result(self, atualizacao, manual: bool) -> None:
        self.update_worker = None
        if atualizacao is None:
            if manual:
                QMessageBox.information(
                    self,
                    "Tudo em dia",
                    f"Você já está usando a versão mais recente ({__version__}).",
                )
            return
        self.pending_update = atualizacao
        self.update_btn.setText(f"⬇ Atualização {atualizacao.versao}")
        self.update_btn.setToolTip(
            f"A versão {atualizacao.versao} do PySusNoCode está disponível — "
            "clique para ver e baixar"
        )
        self.update_btn.show()
        self.toolbar_widget.updateGeometry()
        self.chat.add_app_note(
            f"⬇ Uma nova versão do PySusNoCode está disponível: "
            f"{atualizacao.versao} (você está na {__version__}). Clique em "
            "“⬇ Atualização {v}” na barra acima: eu abro a página de download e "
            "encerro o programa, para que o instalador substitua os arquivos sem "
            "disputa. A instalação é por cima e mantém suas configurações, "
            "lições e notebooks salvos.".replace("{v}", atualizacao.versao)
        )

    def _on_update_failed(self, erro: str, manual: bool) -> None:
        """Mostra o motivo real da falha, não um palpite sobre a internet.

        Até a 1.8.12 esta janela dizia sempre "verifique sua conexão com a
        internet". Numa prefeitura isso mandava o usuário caçar um problema
        inexistente — a internet estava boa, e o bloqueado era o endereço
        api.github.com, que os filtros tratam separadamente de github.com.
        """
        self.update_worker = None
        from ..diag import registrar

        registrar("verificacao de atualizacao falhou", erro)
        if not manual:
            return

        texto = (erro or "").strip()
        if not texto:
            texto = (
                "Não foi possível consultar as atualizações agora. Tente de "
                "novo mais tarde."
            )

        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Warning)
        caixa.setWindowTitle("Não consegui verificar")
        caixa.setText(texto)
        abrir = caixa.addButton(
            "Abrir a página de download", QMessageBox.AcceptRole
        )
        caixa.addButton("Fechar", QMessageBox.RejectRole)
        caixa.exec()
        if caixa.clickedButton() is abrir:
            import webbrowser

            from ..updates import PAGINA_RELEASE

            webbrowser.open(PAGINA_RELEASE)

    def on_check_updates_clicked(self) -> None:
        """Verificação manual, pedida nas Configurações."""
        self._start_update_check(manual=True)

    def on_update_clicked(self) -> None:
        import webbrowser

        from ..updates import PAGINA_RELEASE

        atualizacao = getattr(self, "pending_update", None)
        versao = atualizacao.versao if atualizacao else "mais recente"
        notas = (atualizacao.notas if atualizacao else "") or ""
        texto = (
            f"A versão {versao} está disponível (você usa a {__version__}).\n\n"
            "Ao confirmar, abro a página de download no seu navegador e "
            "**fecho o PySusNoCode**, para que o instalador possa substituir os "
            "arquivos do programa sem disputa. A instalação é feita por cima da "
            "atual e preserva suas configurações, lições aprendidas e notebooks "
            "salvos.\n\n"
            "Se houver trabalho não salvo, vou perguntar antes de fechar."
        ).replace("**", "")
        if notas:
            texto += f"\n\nNovidades desta versão:\n{notas}"

        caixa = QMessageBox(self)
        caixa.setWindowTitle("Atualizar o PySusNoCode")
        caixa.setText(texto)
        caixa.setIcon(QMessageBox.Question)
        baixar_fechar = caixa.addButton(
            "Baixar e fechar o programa", QMessageBox.AcceptRole
        )
        baixar_fechar.setToolTip(
            "Abre a página de download e encerra o PySusNoCode, deixando o "
            "caminho livre para o instalador"
        )
        so_baixar = caixa.addButton(
            "Só abrir a página, sem fechar", QMessageBox.ActionRole
        )
        so_baixar.setToolTip(
            "Útil se você quiser apenas ver as novidades e instalar mais tarde"
        )
        caixa.addButton("Cancelar", QMessageBox.RejectRole)
        caixa.setDefaultButton(baixar_fechar)
        caixa.exec()
        escolhido = caixa.clickedButton()

        if escolhido is so_baixar:
            webbrowser.open(PAGINA_RELEASE)
            self.chat.add_app_note(
                "Abri a página de download no navegador. <b>Feche o PySusNoCode "
                "antes de executar o instalador</b> — instalar com o programa "
                "aberto pode deixar arquivos velhos para trás e abrir duas "
                "janelas depois."
            )
            return

        if escolhido is not baixar_fechar:
            return

        # Trata o trabalho não salvo ANTES de abrir o navegador: perguntar
        # sobre salvar depois que a página abriu confunde, e o usuário pode
        # nem ver a pergunta atrás da janela do navegador.
        if not self._resolve_unsaved("antes de fechar para atualizar"):
            self.chat.add_app_note(
                "Atualização adiada — nada foi fechado. Clique de novo em "
                f"“⬇ Atualização {versao}” quando quiser."
            )
            return

        webbrowser.open(PAGINA_RELEASE)
        # Já resolvemos o que havia para salvar; sem isto o closeEvent
        # perguntaria de novo pela mesma coisa.
        self.dirty = False
        self.encerrando_para_atualizar = True
        QTimer.singleShot(1200, self.close)

    def on_tutorial(self) -> None:
        import webbrowser

        webbrowser.open(VIDEO_TUTORIAL_URL)
        self.chat.add_app_note(
            "🎥 Abri o vídeo tutorial no seu navegador. Ele mostra como pedir uma "
            "análise, executar as células e salvar o notebook."
        )

    def on_appearance(self) -> None:
        dialog = AppearanceDialog(self.config, self)
        if dialog.exec():
            self._apply_appearance()

    def _configurar_atalhos_zoom(self) -> None:
        """Ctrl+ + / Ctrl+ − / Ctrl+0 mudam o tamanho da letra de toda a
        interface (o mesmo ajuste do botão Aparência)."""
        from .atalhos import AUMENTAR, DIMINUIR, ORIGINAL, registrar_atalhos

        registrar_atalhos(self, AUMENTAR, lambda: self.ajustar_letra(+1))
        registrar_atalhos(self, DIMINUIR, lambda: self.ajustar_letra(-1))
        registrar_atalhos(self, ORIGINAL, lambda: self.ajustar_letra(0))

    def ajustar_letra(self, passo: int) -> None:
        atual = int(self.config["font_size"])
        novo = 13 if passo == 0 else max(11, min(24, atual + passo))
        if novo == atual:
            return
        self.config["font_size"] = novo
        self.config.save()
        self._apply_appearance()
        self.statusBar().showMessage(f"Tamanho da letra: {novo} px", 3000)

    def _apply_appearance(self) -> None:
        from PySide6.QtWidgets import QApplication

        t = theme_tokens(self.config["theme"])
        font_px = int(self.config["font_size"])
        app = QApplication.instance()
        apply_app_palette(app, t)
        app.setStyleSheet(app_stylesheet(t))
        self.chat.set_appearance(t, font_px)
        self.notebook_panel.apply_appearance(t, font_px)
        self.brand_logo.setPixmap(logo_pixmap(16, cor=t["muted"]))
        self.brand_label.setText(
            assinatura_html(t["muted"], t["highlight"], max(10, font_px - 2))
        )
        self.toolbar_widget.setStyleSheet(
            f"#barraSuperior{{background:{t['window']};"
            f"border-bottom:1px solid {t['border']};}}"
            f"#barraSuperior QLabel{{color:{t['text']};font-weight:bold;"
            f"font-size:{font_px - 1}px;}}"
            f"#barraSuperior QCheckBox{{color:{t['text']};"
            f"font-size:{font_px - 1}px;}}"
            f"#separadorBarra{{color:{t['border']};background:{t['border']};}}"
            f"#botaoAtualizar{{background:{t['st_ok']};color:#ffffff;"
            f"font-weight:bold;border:1px solid {t['st_ok']};}}"
        )

    def on_settings(self) -> None:
        modelo_antes = (self.config["openai_custom_model"] or "").strip()
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.backend = make_backend(self.config)
            self.autotest_check.setChecked(bool(self.config["autotest"]))

            # Se o modelo personalizado mudou (ou foi apagado), a lista da
            # barra precisa refletir isso na hora — e o modelo novo passa a
            # ser oferecido como escolha.
            modelo_agora = (self.config["openai_custom_model"] or "").strip()
            if modelo_agora != modelo_antes:
                self.config["openai_custom_escolhido"] = False
                if not modelo_agora and int(
                    self.config["openai_model_index"] or 0
                ) >= len(OPENAI_MODELS):
                    # o item que estava escolhido era justamente o personalizado
                    # que acabou de sair da lista: volta para o recomendado.
                    self.config["openai_model_index"] = 0
                self.config.save()
                self._reload_models()
                if modelo_agora and self.config["backend"] == BACKEND_OPENAI:
                    self.chat.add_app_note(
                        f"O modelo personalizado “{modelo_agora}” entrou na lista "
                        "“Modelo”, na barra acima, e já está selecionado. Você pode "
                        "voltar aos modelos padrão por ali a qualquer momento."
                    )
                elif modelo_agora:
                    self.chat.add_app_note(
                        f"O modelo personalizado “{modelo_agora}” foi guardado. Ele "
                        "aparecerá na lista “Modelo” quando você mudar a “Conexão” "
                        "da barra acima para a API da OpenAI / GPT."
                    )

            self._update_status()

    def on_new_conversation(self) -> None:
        if self.phase != PHASE_IDLE:
            QMessageBox.information(
                self, "Aguarde", "Espere a tarefa atual terminar (ou clique em ⏹ Parar)."
            )
            return
        if not self._resolve_unsaved("antes de começar uma nova conversa"):
            return
        self.notebook.clear()
        self.notebook_panel.clear()
        self.backend.reset()
        self.exec_notes = []
        self.fixing_cell = None
        self.pending_queue = []
        self.saved_path = None
        self.dirty = False
        self._update_title()
        self.chat.reset(WELCOME_HTML)
        self._greet_connection()

    # ------------------------------------------------------------------
    # Salvar / abrir notebook (com o contexto da conversa)
    # ------------------------------------------------------------------
    def _mark_dirty(self) -> None:
        if not self.dirty:
            self.dirty = True
            self._update_title()

    def _update_title(self) -> None:
        name = self.saved_path.name if self.saved_path else "notebook novo"
        star = " •" if self.dirty else ""
        self.setWindowTitle(
            f"{APP_NAME} {__version__} — {name}{star} — análises do DATASUS sem programar"
        )

    def _context_metadata(self) -> dict:
        meta = {
            "versao": __version__,
            "salvo_em": datetime.now().isoformat(timespec="seconds"),
            "conexao": self.config["backend"],
            "chat": self.chat.export_entries(),
        }
        session_id = getattr(self.backend, "session_id", None)
        if session_id:
            meta["sessao_claude"] = session_id
        history = getattr(self.backend, "history", None)
        if history:
            meta["historico_api"] = history
        return meta

    def on_save_notebook(self) -> bool:
        """Salva o notebook (.ipynb) com o contexto do chat nos metadados.
        Devolve True se o arquivo foi salvo."""
        if not self.notebook.cells:
            QMessageBox.information(
                self, "Notebook vazio", "Ainda não há células para salvar."
            )
            return False
        path = self.saved_path
        first_save = path is None
        if first_save:
            NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)
            chosen, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar notebook",
                str(NOTEBOOKS_DIR / "analise_pysus.ipynb"),
                "Notebook Jupyter (*.ipynb)",
            )
            if not chosen:
                return False
            path = Path(chosen)
        try:
            self.notebook.save_ipynb(path, self._context_metadata())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Erro ao salvar", f"Não consegui salvar o notebook:\n{exc}"
            )
            return False
        self.saved_path = path
        self.dirty = False
        self._update_title()
        self.statusBar().showMessage(f"💾 Notebook salvo em {path}", 8000)
        if first_save:
            QMessageBox.information(
                self,
                "Notebook salvo",
                f"Notebook salvo em:\n{path}\n\nA conversa foi salva junto: ao abrir "
                "este arquivo pelo botão “📂 Abrir”, o chat volta de onde parou.\n\n"
                "Para usar no Google Colab: abra colab.research.google.com, clique "
                "em “Upload” e escolha esse arquivo.",
            )
        return True

    def on_open_example(self) -> None:
        """Abre uma das análises prontas do repositório de exemplos."""
        if self.phase != PHASE_IDLE:
            QMessageBox.information(self, "Aguarde", "Espere a tarefa atual terminar.")
            return
        if not self._resolve_unsaved("antes de abrir um exemplo"):
            return

        from .. import exemplos as cat
        from .exemplos_dialog import ExemplosDialog

        janela = ExemplosDialog(int(self.config["font_size"]), self)
        if janela.exec() != QDialog.Accepted or not janela.escolhido:
            return
        escolhido = janela.escolhido

        # O download pode levar alguns segundos: alguns exemplos passam de
        # 300 KB por causa dos gráficos já salvos.
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            caminho, origem = cat.obter_notebook(escolhido["arquivo"])
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(
                self,
                "Não consegui abrir o exemplo",
                f"O exemplo “{escolhido.get('titulo','')}” não pôde ser obtido.\n\n"
                f"{exc}\n\nSe a rede deste computador for controlada, você pode ver "
                f"os exemplos pelo navegador em {cat.PAGINA}.",
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        from ..nb import Notebook

        temp = Notebook()
        try:
            temp.load_ipynb(str(caminho))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Erro ao abrir", f"Não consegui ler o exemplo:\n{exc}"
            )
            return

        self.notebook_panel.clear()
        self.notebook.cells = temp.cells
        for cell in self.notebook.cells:
            self.notebook_panel.add_cell(cell)

        self.backend.reset()
        self.chat.reset(WELCOME_HTML)
        self.exec_notes = []
        self.fixing_cell = None
        self.pending_queue = []
        # De propósito sem caminho salvo: o exemplo é um ponto de partida, e
        # "Salvar" deve perguntar onde gravar em vez de sobrescrever a cópia
        # baixada, que fica numa pasta temporária.
        self.saved_path = None
        self.dirty = False
        self._update_title()

        procedencia = (
            "baixado agora do GitHub, na versão mais recente"
            if origem == cat.ORIGEM_GITHUB
            else "aberto da cópia que veio no instalador"
        )
        self.chat.add_app_note(
            f"📚 Exemplo aberto: <b>{escolhido.get('titulo','')}</b> "
            f"({len(self.notebook.cells)} células, {procedencia}).<br><br>"
            "As saídas que você vê são as da última validação. Para rodar com "
            "dados de agora, clique em “▶▶ Executar tudo”. Se quiser adaptar — "
            "outro estado, outro ano, outro recorte — é só pedir aqui no chat."
        )
        self.exec_notes.append(
            f"O usuário abriu o exemplo pronto “{escolhido.get('titulo','')}” "
            f"({escolhido['arquivo']}). Ele já funciona; ao alterar, preserve a "
            "estrutura e explique o que mudou."
        )

    def on_open_notebook(self) -> None:
        if self.phase != PHASE_IDLE:
            QMessageBox.information(self, "Aguarde", "Espere a tarefa atual terminar.")
            return
        if not self._resolve_unsaved("antes de abrir outro notebook"):
            return
        start_dir = NOTEBOOKS_DIR if NOTEBOOKS_DIR.exists() else Path.home()
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Abrir notebook", str(start_dir), "Notebook Jupyter (*.ipynb)"
        )
        if not chosen:
            return

        from ..nb import Notebook

        temp = Notebook()
        try:
            meta = temp.load_ipynb(chosen)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Erro ao abrir", f"Não consegui abrir o notebook:\n{exc}"
            )
            return

        self.notebook_panel.clear()
        self.notebook.cells = temp.cells
        for cell in self.notebook.cells:
            self.notebook_panel.add_cell(cell)

        self.backend.reset()
        if meta.get("sessao_claude") and hasattr(self.backend, "session_id"):
            self.backend.session_id = meta["sessao_claude"]
        if meta.get("historico_api") and hasattr(self.backend, "history"):
            self.backend.history = meta["historico_api"]

        if meta.get("chat"):
            self.chat.restore_entries(meta["chat"])
            contexto = "a conversa anterior foi restaurada"
        else:
            self.chat.reset(WELCOME_HTML)
            contexto = "este arquivo não tinha conversa salva"

        self.exec_notes = []
        self.fixing_cell = None
        self.pending_queue = []
        self.saved_path = Path(chosen)
        self.dirty = False
        self._update_title()
        n_cells = len(self.notebook.cells)
        self.chat.add_app_note(
            f"📂 Notebook aberto: {self.saved_path.name} ({n_cells} células) — "
            f"{contexto}. As variáveis ainda não estão na memória: use "
            "“▶▶ Executar tudo” para recarregar os dados antes de continuar a análise."
        )
        conexao_salva = meta.get("conexao")
        if conexao_salva and conexao_salva != self.config["backend"]:
            de = assistant_name(conexao_salva)
            para = self._assistant()
            if de != para:
                self.chat.add_app_note(
                    f"ℹ Esta conversa foi criada com o {de} e agora você está "
                    f"conectado ao {para}. O texto da conversa foi preservado, mas "
                    f"o {para} começa sem a memória interna do diálogo anterior — "
                    "se algo ficar confuso, reformule o próximo pedido com os "
                    "detalhes importantes."
                )

    def _ask_save_choice(self, acao: str) -> str:
        """Pergunta o que fazer com alterações não salvas.
        Devolve 'salvar', 'descartar' ou 'cancelar'."""
        box = QMessageBox(self)
        box.setWindowTitle("Salvar notebook?")
        box.setText(
            f"O notebook atual tem alterações não salvas.\nDeseja salvá-lo {acao}?"
        )
        salvar = box.addButton("💾 Salvar", QMessageBox.AcceptRole)
        box.addButton("Continuar sem salvar", QMessageBox.DestructiveRole)
        cancelar = box.addButton("Cancelar", QMessageBox.RejectRole)
        box.setDefaultButton(salvar)
        box.exec()
        clicked = box.clickedButton()
        if clicked is salvar:
            return "salvar"
        if clicked is cancelar:
            return "cancelar"
        return "descartar"

    def _resolve_unsaved(self, acao: str) -> bool:
        """Garante que alterações não salvas foram tratadas.
        Devolve False se o usuário cancelou a ação."""
        if not (self.dirty and self.notebook.cells):
            return True
        choice = self._ask_save_choice(acao)
        if choice == "cancelar":
            return False
        if choice == "salvar":
            return self.on_save_notebook()
        return True

    # ------------------------------------------------------------------
    # Conversa com o Claude
    # ------------------------------------------------------------------
    def on_user_send(self, text: str) -> None:
        if self.phase != PHASE_IDLE:
            return
        self.chat.add_user(text)
        self._mark_dirty()
        prompt = text
        if self.exec_notes:
            notes = "\n".join(self.exec_notes[-6:])
            prompt = (
                f"(Contexto do aplicativo — resultados de execuções recentes:\n{notes})\n\n"
                f"Pedido do usuário: {text}"
            )
            self.exec_notes = []
        self._start_llm_turn(prompt, f"O {self._assistant()} está pensando…")

    def _start_llm_turn(self, prompt: str, status: str) -> None:
        self._set_phase(PHASE_LLM, status)
        self.chat.begin_stream()
        worker = LLMWorker(
            self.backend, prompt, self._system_prompt(), self._current_model(), self
        )
        worker.chunk.connect(self.chat.stream_chunk)
        worker.done.connect(self.on_llm_done)
        worker.failed.connect(self.on_llm_failed)
        self.llm_worker = worker
        worker.start()

    def on_llm_done(self, full_text: str) -> None:
        cancelled = self.llm_worker is not None and self.llm_worker.cancel.is_set()
        self.llm_worker = None
        if cancelled:
            self.chat.end_stream(None)
            self.chat.add_app_note("⏹ Geração interrompida.")
            self._abort_flow()
            return

        # A numeração mostrada no chat precisa bater com a posição real da
        # célula no notebook — e, no fluxo de correção, apontar a célula que
        # está sendo substituída.
        if self.fixing_cell is not None and self.fixing_cell in self.notebook.cells:
            numero_inicial = self.notebook.index_of(self.fixing_cell) + 1
            verbo = "corrigida no"
        else:
            numero_inicial = len(self.notebook.cells) + 1
            verbo = "adicionada ao"
        parsed = parse_response(full_text, numero_inicial, verbo)
        self.chat.end_stream(parsed.chat_text or "(célula gerada)")
        self._mark_dirty()

        new_lessons = 0
        for lesson in parsed.lessons:
            if self.lessons.add(lesson):
                new_lessons += 1
        if new_lessons:
            self.chat.add_app_note(
                f"🧠 Aprendi {new_lessons} lição(ões) nova(s) com este caso — vou "
                "lembrar disso nas próximas análises."
            )

        if self.fixing_cell is not None:
            self._apply_fix(parsed)
            return

        ran_anything = False
        for parsed_cell in parsed.cells:
            cell = self.notebook.add(parsed_cell.kind, parsed_cell.source)
            self.notebook_panel.add_cell(cell)
            if parsed_cell.kind == "code" and self.autotest_check.isChecked():
                self.pending_queue.append(cell)
                ran_anything = True

        if ran_anything:
            self._run_next()
        else:
            self._set_phase(PHASE_IDLE)

    def on_llm_failed(self, message: str) -> None:
        cancelled = self.llm_worker is not None and self.llm_worker.cancel.is_set()
        self.llm_worker = None
        self.chat.end_stream(None)
        if cancelled:
            self.chat.add_app_note("⏹ Geração interrompida.")
        else:
            self.chat.add_error(message)
        self._abort_flow()

    def _abort_flow(self) -> None:
        if self.fixing_cell is not None:
            self.fixing_cell.status = STATUS_ERROR
            widget = self.notebook_panel.widget_for(self.fixing_cell)
            if widget:
                widget.refresh()
            self.fixing_cell = None
        self.pending_queue = []
        self._set_phase(PHASE_IDLE)

    # ------------------------------------------------------------------
    # Execução de células
    # ------------------------------------------------------------------
    def _start_kernel(self, restart: bool = False) -> None:
        if self.kernel_state == "starting":
            return
        self.kernel_state = "starting"
        self._update_status()
        worker = KernelStartWorker(self.kernel, restart=restart, parent=self)
        worker.ready.connect(self._on_kernel_ready)
        worker.failed.connect(self._on_kernel_failed)
        self.kernel_worker = worker
        worker.start()

    def _on_kernel_ready(self) -> None:
        self.kernel_worker = None
        self.kernel_state = "ready"
        self._update_status()
        if self.pending_queue and self.phase != PHASE_LLM:
            self._run_next()

    def _on_kernel_failed(self, message: str) -> None:
        self.kernel_worker = None
        self.kernel_state = "off"
        self.chat.add_error(
            message + "\nAs células não poderão ser executadas dentro do aplicativo, "
            "mas você ainda pode copiá-las para o Google Colab."
        )
        self.pending_queue = []
        self._set_phase(PHASE_IDLE)

    def on_restart_kernel(self) -> None:
        if self.phase != PHASE_IDLE:
            QMessageBox.information(self, "Aguarde", "Espere a tarefa atual terminar.")
            return
        for cell in self.notebook.cells:
            if cell.kind == "code" and cell.status in (STATUS_OK, STATUS_ERROR):
                cell.status = STATUS_NEW
                widget = self.notebook_panel.widget_for(cell)
                if widget:
                    widget.refresh()
        self.chat.add_app_note(
            "🔄 Reiniciando o kernel Python. As variáveis carregadas foram limpas — "
            "execute as células novamente quando precisar delas."
        )
        self._start_kernel(restart=True)

    def on_run_cell_clicked(self, widget) -> None:
        if self.phase != PHASE_IDLE:
            return
        self.pending_queue = [widget.cell]
        self._run_next()

    def on_run_all(self) -> None:
        if self.phase != PHASE_IDLE:
            return
        self.pending_queue = [c for c in self.notebook.cells if c.kind == "code"]
        if self.pending_queue:
            self._run_next()

    def on_fix_cell_clicked(self, widget) -> None:
        if self.phase != PHASE_IDLE:
            return
        cell = widget.cell
        error = self._last_error_text(cell) or "(erro não registrado; execute a célula novamente)"
        cell.fix_attempts = 1
        self.fixing_cell = cell
        self._request_fix(cell, error)

    def _run_next(self) -> None:
        if not self.pending_queue:
            self._set_phase(PHASE_IDLE)
            return
        if self.kernel_state != "ready":
            self._set_phase(PHASE_EXEC, "Iniciando o kernel Python…")
            if self.kernel_state == "off":
                self._start_kernel()
            return
        cell = self.pending_queue.pop(0)
        self._run_cell(cell)

    def _run_cell(self, cell: Cell) -> None:
        index = self.notebook.index_of(cell) + 1
        self.current_cell = cell
        cell.status = STATUS_RUNNING
        cell.outputs = []
        widget = self.notebook_panel.widget_for(cell)
        if widget:
            widget.refresh()
            self.notebook_panel.scroll_to_widget(widget)
        self._set_phase(PHASE_EXEC, f"Executando a célula {index}…")

        worker = CellRunWorker(
            self.kernel, cell.source, float(self.config["cell_timeout"]), self
        )
        worker.output.connect(lambda out, c=cell: self._on_cell_output(c, out))
        worker.done.connect(lambda result, c=cell: self._on_cell_done(c, result))
        worker.failed.connect(self._on_cell_crashed)
        self.cell_worker = worker
        worker.start()

    def _on_cell_output(self, cell: Cell, output: dict) -> None:
        cell.outputs.append(output)
        widget = self.notebook_panel.widget_for(cell)
        if widget:
            widget.render_outputs()

    def _on_cell_done(self, cell: Cell, result) -> None:
        self.cell_worker = None
        self.current_cell = None
        # As saídas já chegaram uma a uma via _on_cell_output.
        cell.execution_count = result.execution_count
        self._mark_dirty()
        index = self.notebook.index_of(cell) + 1
        widget = self.notebook_panel.widget_for(cell)

        if result.ok:
            cell.status = STATUS_OK
            if widget:
                widget.refresh()
            self.exec_notes.append(
                f"Célula {index} executada com sucesso. Saída: "
                f"{self._summarize_outputs(cell.outputs)}"
            )
            if self.fixing_cell is cell:
                self.fixing_cell = None
                cell.fix_attempts = 0
                self.chat.add_app_note(
                    f"✅ Célula {index} corrigida e executada com sucesso."
                )
            self._run_next()
            return

        cell.status = STATUS_ERROR
        if widget:
            widget.refresh()
        error = result.error_summary or "(erro desconhecido)"
        max_attempts = int(self.config["max_fix_attempts"])

        # O Python morreu (quase sempre falta de memória): não adianta pedir
        # correção à IA — é preciso um kernel novo antes de qualquer coisa.
        if getattr(result, "kernel_morreu", False):
            self.fixing_cell = None
            self.pending_queue = []
            self.kernel_state = "off"
            for outra in self.notebook.cells:
                if outra.kind == "code" and outra.status == STATUS_OK:
                    outra.status = STATUS_NEW
                    w = self.notebook_panel.widget_for(outra)
                    if w:
                        w.refresh()
            self.chat.add_app_note(
                f"⚠ O Python foi encerrado ao executar a célula {index} — "
                "normalmente por falta de memória, quando uma base do DATASUS é "
                "grande demais para caber inteira. Estou preparando um Python novo; "
                "quando terminar, execute as células novamente, de preferência com "
                "um recorte menor (um estado, um mês) ou pedindo só as colunas "
                "necessárias."
            )
            self.exec_notes.append(
                f"A célula {index} encerrou o Python por consumo de memória. "
                "Refaça essa etapa com um recorte menor ou lendo apenas as colunas "
                "necessárias (as_dataframe=False + pd.read_parquet(columns=[...]))."
            )
            self._start_kernel(restart=False)
            self._set_phase(PHASE_IDLE)
            return

        # Erro do ambiente, não do código: a IA não tem o que corrigir, e
        # tentar só gastaria as tentativas de correção.
        ambiente = erro_de_ambiente(error)
        if ambiente:
            self.fixing_cell = None
            self.pending_queue = []
            self.chat.add_app_note(f"⚠ Célula {index}: {ambiente}")
            self.exec_notes.append(
                f"A célula {index} falhou por um problema de ambiente, não de "
                f"código: {ambiente.splitlines()[0]} Não reescreva a célula."
            )
            self._set_phase(PHASE_IDLE)
            return

        if (
            self.autotest_check.isChecked()
            and not result.timed_out
            and cell.fix_attempts < max_attempts
        ):
            cell.fix_attempts += 1
            self.fixing_cell = cell
            self.chat.add_app_note(
                f"🔧 A célula {index} falhou. Corrigindo automaticamente "
                f"(tentativa {cell.fix_attempts} de {max_attempts})…"
            )
            self._request_fix(cell, error)
        else:
            self.fixing_cell = None
            self.pending_queue = []
            if result.timed_out:
                self.chat.add_app_note(
                    f"⏱ A célula {index} excedeu o tempo limite e foi interrompida. "
                    f"Você pode aumentar o tempo nas Configurações ou pedir ao {self._assistant()} "
                    "uma versão mais leve (menos anos/UFs)."
                )
            else:
                self.chat.add_app_note(
                    f"❌ Não consegui corrigir a célula {index} automaticamente. "
                    "Você pode editar o código, clicar em “🔧 Corrigir com IA” para "
                    "tentar de novo, ou descrever no chat o que deseja."
                )
                self.exec_notes.append(
                    f"Célula {index} continua falhando após tentativas de correção. "
                    f"Último erro: {error[-600:]}"
                )
            self._set_phase(PHASE_IDLE)

    def _on_cell_crashed(self, message: str) -> None:
        self.cell_worker = None
        self.current_cell = None
        self.chat.add_error(message)
        self.fixing_cell = None
        self.pending_queue = []
        self._set_phase(PHASE_IDLE)

    def _request_fix(self, cell: Cell, error: str) -> None:
        index = self.notebook.index_of(cell) + 1
        prompt = FIX_PROMPT_TEMPLATE.format(
            cell_number=index,
            attempt=cell.fix_attempts,
            max_attempts=int(self.config["max_fix_attempts"]),
            code=cell.source,
            error=error[-3000:],
        )
        self._start_llm_turn(
            prompt, f"O {self._assistant()} está corrigindo a célula {index}…"
        )

    def _apply_fix(self, parsed) -> None:
        cell = self.fixing_cell
        code_cells = [c for c in parsed.cells if c.kind == "code"]
        if cell is None or not code_cells:
            self.chat.add_app_note(
                f"O {self._assistant()} não devolveu uma célula corrigida. Tente clicar em "
                "“🔧 Corrigir com IA” novamente ou descreva o problema no chat."
            )
            self._abort_flow()
            return
        widget = self.notebook_panel.widget_for(cell)
        if widget:
            widget.set_source(code_cells[0].source)
        else:
            cell.source = code_cells[0].source
        self._run_cell(cell)

    # ------------------------------------------------------------------
    def on_stop(self) -> None:
        if self.llm_worker is not None:
            self.llm_worker.cancel.set()
            self.chat.set_busy(True, f"Interrompendo o {self._assistant()}…")
        elif self.cell_worker is not None:
            self.kernel.interrupt()
            self.chat.set_busy(True, "Interrompendo a célula…")

    @staticmethod
    def _summarize_outputs(outputs: list[dict], limit: int = 700) -> str:
        texts: list[str] = []
        for out in outputs:
            otype = out.get("output_type")
            if otype == "stream":
                texts.append(out.get("text", ""))
            elif otype in ("execute_result", "display_data"):
                data = out.get("data", {})
                if "text/plain" in data:
                    texts.append(str(data["text/plain"]))
                elif "image/png" in data:
                    texts.append("[gráfico gerado]")
            elif otype == "error":
                texts.append("\n".join(out.get("traceback", [])[-5:]))
        joined = "\n".join(t for t in texts if t).strip()
        if not joined:
            return "(sem saída de texto)"
        if len(joined) > limit:
            half = limit // 2
            joined = joined[:half] + "\n…(saída cortada)…\n" + joined[-half:]
        return joined

    @staticmethod
    def _last_error_text(cell: Cell) -> str:
        for out in reversed(cell.outputs):
            if out.get("output_type") == "error":
                return "\n".join(out.get("traceback", []))
        return ""

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._resolve_unsaved("antes de sair"):
            event.ignore()
            return
        if self.llm_worker is not None:
            self.llm_worker.cancel.set()
        self.kernel.shutdown()
        # Espera as threads de trabalho terminarem para um encerramento limpo.
        for worker in (self.kernel_worker, self.cell_worker, self.llm_worker):
            if worker is not None:
                worker.wait(5000)
        event.accept()
