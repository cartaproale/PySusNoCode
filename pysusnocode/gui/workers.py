"""Threads de trabalho: chamadas à IA e execução de células no kernel."""

from __future__ import annotations

import threading
from time import monotonic

from PySide6.QtCore import QThread, Signal

from .. import tempos
from ..kernel import ExecResult, NotebookKernel
from ..llm import LLMError


class _Interrompido(Exception):
    """Cancelamento do usuario: sai do cronometro sem virar medicao."""


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
            # O tempo e medido aqui, e nao na janela: e daqui que da para separar
            # a espera da IA da espera do kernel, que sao coisas diferentes.
            with tempos.Cronometro(tempos.IA, str(self.model or "")) as relogio:

                def ao_receber(pedaco: str) -> None:
                    relogio.primeira_resposta()
                    self.chunk.emit(pedaco)

                text = self.backend.send(
                    self.user_text,
                    self.system_prompt,
                    self.model,
                    ao_receber,
                    self.cancel,
                )
                if self.cancel.is_set():
                    raise _Interrompido
            self.done.emit(text)
        except _Interrompido:
            # Cancelado pelo usuario: nao e resposta, nao vira estatistica.
            self.done.emit(text)
        except LLMError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Erro inesperado ao falar com a IA: {exc}")


class UpdateCheckWorker(QThread):
    """Consulta a última versão publicada, sem travar a interface."""

    resultado = Signal(object)   # Atualizacao | None
    falhou = Signal(str)

    def run(self) -> None:
        try:
            from ..updates import verificar

            self.resultado.emit(verificar())
        except Exception as exc:  # noqa: BLE001
            # Sem internet ou GitHub fora do ar: não incomodar o usuário.
            self.falhou.emit(str(exc))


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
            inicio = monotonic()
            result: ExecResult = self.kernel.execute(
                self.code, timeout=self.timeout, on_output=self.output.emit
            )
            # Estouro de tempo e morte do kernel nao sao "quanto isto demora":
            # sao o limite que nos mesmos impusemos e um acidente. Entrariam na
            # media como dez minutos e assustariam quem so queria saber se da
            # tempo de tomar um cafe. Celula que falhou rapido, essa conta.
            if not result.timed_out and not result.kernel_morreu:
                tempos.registrar(tempos.CELULA, monotonic() - inicio)
            self.done.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"Falha ao executar a célula: {exc}")
