"""Threads de trabalho: chamadas ao Claude e execução de células no kernel."""

from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from ..kernel import ExecResult, NotebookKernel
from ..llm import LLMError


class LLMWorker(QThread):
    chunk = Signal(str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, backend, user_text: str, system_prompt: str, model, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.user_text = user_text
        self.system_prompt = system_prompt
        self.model = model
        self.cancel = threading.Event()

    def run(self) -> None:
        try:
            text = self.backend.send(
                self.user_text,
                self.system_prompt,
                self.model,
                self.chunk.emit,
                self.cancel,
            )
            self.done.emit(text)
        except LLMError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Erro inesperado ao falar com o Claude: {exc}")


class KernelStartWorker(QThread):
    ready = Signal()
    failed = Signal(str)

    def __init__(self, kernel: NotebookKernel, restart: bool = False, parent=None):
        super().__init__(parent)
        self.kernel = kernel
        self.restart = restart

    def run(self) -> None:
        try:
            if self.restart:
                self.kernel.restart()
            else:
                self.kernel.start()
            self.ready.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Não consegui iniciar o kernel Python: {exc}")


class CellRunWorker(QThread):
    output = Signal(object)      # dict de saída (formato nbformat)
    done = Signal(object)        # ExecResult
    failed = Signal(str)

    def __init__(self, kernel: NotebookKernel, code: str, timeout: float, parent=None):
        super().__init__(parent)
        self.kernel = kernel
        self.code = code
        self.timeout = timeout

    def run(self) -> None:
        try:
            result: ExecResult = self.kernel.execute(
                self.code, timeout=self.timeout, on_output=self.output.emit
            )
            self.done.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Falha ao executar a célula: {exc}")
