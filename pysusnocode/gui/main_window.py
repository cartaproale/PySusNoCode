"""Janela principal do PySusNoCode.

Orquestra o ciclo: pedido do usuário → Claude propõe células → o app executa
cada célula no kernel → em caso de erro, pede correção ao Claude (até N
tentativas) → registra a lição aprendida para as próximas sessões.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
)

from .. import APP_NAME, __version__
from ..config import BACKEND_AGENT, BACKEND_API, MODELS, NOTEBOOKS_DIR, Config, find_claude_cli
from ..kernel import NotebookKernel
from ..lessons import LessonStore
from ..llm import make_backend
from ..nb import STATUS_ERROR, STATUS_NEW, STATUS_OK, STATUS_RUNNING, Cell, Notebook
from ..prompts import FIX_PROMPT_TEMPLATE, WELCOME_HTML, build_system_prompt
from ..protocol import parse_response
from ..theme import apply_app_palette, tokens as theme_tokens
from .appearance_dialog import AppearanceDialog
from .chat_panel import ChatPanel
from .notebook_panel import NotebookPanel
from .settings_dialog import SettingsDialog
from .workers import CellRunWorker, KernelStartWorker, LLMWorker

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

        self._update_title()
        self.resize(1360, 840)

        self._build_toolbar()

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
        self.notebook_panel.changed.connect(self._mark_dirty)
        splitter.addWidget(self.notebook_panel)
        splitter.setSizes([520, 840])
        self.setCentralWidget(splitter)

        self.status_label = QLabel()
        self.statusBar().addWidget(self.status_label)

        if self.config["always_on_top"]:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self._apply_appearance()
        self.chat.reset(WELCOME_HTML)
        self._greet_connection()
        self._update_status()
        self._start_kernel()

    # ------------------------------------------------------------------
    # Barra superior
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        bar = QToolBar()
        bar.setMovable(False)
        self.addToolBar(bar)

        new_btn = QPushButton("🆕 Nova conversa")
        new_btn.setToolTip("Começar uma nova conversa e um notebook em branco")
        new_btn.clicked.connect(self.on_new_conversation)
        bar.addWidget(new_btn)
        bar.addSeparator()

        bar.addWidget(QLabel(" Modelo: "))
        self.model_combo = QComboBox()
        for label, _api_id, _cli_id in MODELS:
            self.model_combo.addItem(label)
        self.model_combo.setCurrentIndex(int(self.config["model_index"]))
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        bar.addWidget(self.model_combo)

        bar.addWidget(QLabel("  Conexão: "))
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Conta claude.ai (Claude Code)")
        self.backend_combo.addItem("API Anthropic (chave)")
        self.backend_combo.setCurrentIndex(
            0 if self.config["backend"] == BACKEND_AGENT else 1
        )
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        bar.addWidget(self.backend_combo)

        self.login_btn = QPushButton("🔑 Entrar (claude.ai)")
        self.login_btn.setToolTip(
            "Abrir o Claude Code em uma janela para fazer login na sua conta claude.ai"
        )
        self.login_btn.clicked.connect(self.on_login)
        bar.addWidget(self.login_btn)
        bar.addSeparator()

        self.autotest_check = QCheckBox(" Autoteste e correção automática ")
        self.autotest_check.setToolTip(
            "Executar automaticamente cada célula criada pelo Claude e corrigir erros sozinho"
        )
        self.autotest_check.setChecked(bool(self.config["autotest"]))
        self.autotest_check.toggled.connect(self._on_autotest_toggled)
        bar.addWidget(self.autotest_check)

        self.pin_check = QCheckBox(" 📌 Sempre visível ")
        self.pin_check.setToolTip(
            "Manter a janela do PySusNoCode acima de todas as outras janelas"
        )
        self.pin_check.setChecked(bool(self.config["always_on_top"]))
        self.pin_check.toggled.connect(self._on_pin_toggled)
        bar.addWidget(self.pin_check)
        bar.addSeparator()

        appearance_btn = QPushButton("🎨 Aparência")
        appearance_btn.setToolTip(
            "Acessibilidade: escolher tema claro ou escuro e o tamanho da letra"
        )
        appearance_btn.clicked.connect(self.on_appearance)
        bar.addWidget(appearance_btn)

        settings_btn = QPushButton("⚙ Configurações")
        settings_btn.clicked.connect(self.on_settings)
        bar.addWidget(settings_btn)

    # ------------------------------------------------------------------
    # Estado / status
    # ------------------------------------------------------------------
    def _greet_connection(self) -> None:
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
        backend_txt = (
            "conta claude.ai" if self.config["backend"] == BACKEND_AGENT else "API Anthropic"
        )
        self.status_label.setText(
            f"  {kernel_txt}  ·  conexão: {backend_txt}  ·  "
            f"lições aprendidas: {self.lessons.count()}"
        )

    def _set_phase(self, phase: str, status: str = "") -> None:
        self.phase = phase
        self.chat.set_busy(phase != PHASE_IDLE, status)
        self._update_status()

    def _model_ids(self) -> tuple[str | None, str | None]:
        _label, api_id, cli_id = MODELS[self.model_combo.currentIndex()]
        return api_id, cli_id

    def _current_model(self) -> str | None:
        api_id, cli_id = self._model_ids()
        return cli_id if self.config["backend"] == BACKEND_AGENT else api_id

    def _system_prompt(self) -> str:
        return build_system_prompt(self.lessons.for_prompt())

    # ------------------------------------------------------------------
    # Ações da barra
    # ------------------------------------------------------------------
    def _on_model_changed(self, index: int) -> None:
        self.config["model_index"] = index
        self.config.save()

    def _on_backend_changed(self, index: int) -> None:
        self.config["backend"] = BACKEND_AGENT if index == 0 else BACKEND_API
        self.config.save()
        self.backend = make_backend(self.config)
        self.chat.add_app_note(
            "Modo de conexão alterado. A conversa com o Claude recomeça do zero "
            "(o notebook continua intacto)."
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

    def on_appearance(self) -> None:
        dialog = AppearanceDialog(self.config, self)
        if dialog.exec():
            self._apply_appearance()

    def _apply_appearance(self) -> None:
        from PySide6.QtWidgets import QApplication

        t = theme_tokens(self.config["theme"])
        font_px = int(self.config["font_size"])
        apply_app_palette(QApplication.instance(), t)
        self.chat.set_appearance(t, font_px)
        self.notebook_panel.apply_appearance(t, font_px)

    def on_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.backend = make_backend(self.config)
            self.autotest_check.setChecked(bool(self.config["autotest"]))
            self.backend_combo.setCurrentIndex(
                0 if self.config["backend"] == BACKEND_AGENT else 1
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
        self._start_llm_turn(prompt, "O Claude está pensando…")

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

        parsed = parse_response(full_text)
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
                    "Você pode aumentar o tempo nas Configurações ou pedir ao Claude "
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
        self._start_llm_turn(prompt, f"O Claude está corrigindo a célula {index}…")

    def _apply_fix(self, parsed) -> None:
        cell = self.fixing_cell
        code_cells = [c for c in parsed.cells if c.kind == "code"]
        if cell is None or not code_cells:
            self.chat.add_app_note(
                "O Claude não devolveu uma célula corrigida. Tente clicar em "
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
            self.chat.set_busy(True, "Interrompendo o Claude…")
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
