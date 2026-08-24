"""Kernel Jupyter embutido do PySusNoCode.

As células do notebook rodam num kernel IPython real (o mesmo motor do Jupyter
e do Google Colab), então o estado (variáveis, DataFrames) persiste entre
células e `%pip install` funciona. Todas as chamadas aqui são bloqueantes e
devem rodar em thread de trabalho.
"""

from __future__ import annotations

import queue
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


@dataclass
class ExecResult:
    ok: bool
    outputs: list[dict] = field(default_factory=list)
    error_summary: str = ""          # ename + evalue + traceback (sem cores)
    execution_count: int | None = None
    timed_out: bool = False
    kernel_morreu: bool = False      # o Python parou (estouro de memória, etc.)


MENSAGEM_KERNEL_MORTO = (
    "O Python foi encerrado no meio da execução desta célula.\n\n"
    "A causa quase sempre é falta de memória: alguma base do DATASUS é grande "
    "demais para ser carregada inteira (a de dengue de um ano, por exemplo, "
    "ocupa dezenas de gigabytes).\n\n"
    "O que costuma resolver:\n"
    "• baixar um recorte menor (um estado, um mês);\n"
    "• pedir só as colunas necessárias em vez da tabela inteira;\n"
    "• fechar outros programas pesados e tentar de novo.\n\n"
    "As variáveis carregadas antes foram perdidas — execute as células "
    "anteriores novamente antes de continuar."
)


class NotebookKernel:
    def __init__(self) -> None:
        self.km = None
        self.kc = None

    # ------------------------------------------------------------------
    @property
    def alive(self) -> bool:
        try:
            return self.km is not None and self.km.is_alive()
        except Exception:  # noqa: BLE001
            return False

    def start(self) -> None:
        from jupyter_client.manager import KernelManager

        km = KernelManager(kernel_name="python3")
        km.start_kernel()
        kc = km.client()
        kc.start_channels()
        kc.wait_for_ready(timeout=120)
        self.km, self.kc = km, kc
        self._setup()

    def restart(self) -> None:
        if self.km is None:
            self.start()
            return
        self.km.restart_kernel(now=True)
        self.kc.wait_for_ready(timeout=120)
        self._setup()

    def _setup(self) -> None:
        """Prepara o kernel como um notebook do Colab.

        O nest_asyncio é obrigatório para a biblioteca PySUS: as funções dela
        chamam asyncio.run() internamente, o que falha dentro de um kernel
        Jupyter ("asyncio.run() cannot be called from a running event loop").
        Aplicar aqui garante que funcione mesmo que a célula não peça.
        """
        preparo = (
            "%matplotlib inline\n"
            "try:\n"
            "    import nest_asyncio as _na\n"
            "    _na.apply()\n"
            "    del _na\n"
            "except Exception:\n"
            "    pass\n"
            # As tabelas do DATASUS têm de 60 a 360 colunas; com os padrões do
            # pandas elas saem espremidas em 80 caracteres e ilegíveis.
            # Só mexemos em quebra de linha: nada aqui pode alterar o valor
            # mostrado, senão a mesma célula exibiria números diferentes aqui e
            # no Colab. (Um float_format global arredondava 0,0886 para 0,09.)
            "try:\n"
            "    import pandas as _pd\n"
            "    _pd.set_option('display.width', 180)\n"
            "    _pd.set_option('display.max_columns', 40)\n"
            "    del _pd\n"
            "except Exception:\n"
            "    pass\n"
        )
        try:
            self.execute(preparo, timeout=60)
        except Exception:  # noqa: BLE001
            pass

    def interrupt(self) -> None:
        if self.km is not None:
            try:
                self.km.interrupt_kernel()
            except Exception:  # noqa: BLE001
                pass

    def shutdown(self) -> None:
        try:
            if self.kc is not None:
                self.kc.stop_channels()
            if self.km is not None:
                self.km.shutdown_kernel(now=True)
        except Exception:  # noqa: BLE001
            pass
        self.km = self.kc = None

    # ------------------------------------------------------------------
    def execute(
        self,
        code: str,
        timeout: float = 600,
        on_output: Callable[[dict], None] | None = None,
    ) -> ExecResult:
        """Executa `code` e coleta as saídas no formato do nbformat."""
        if self.kc is None:
            raise RuntimeError("O kernel ainda não foi iniciado.")

        msg_id = self.kc.execute(code, allow_stdin=False)
        result = ExecResult(ok=True)
        deadline = monotonic() + timeout

        while True:
            if monotonic() > deadline:
                self.interrupt()
                result.ok = False
                result.timed_out = True
                result.error_summary = (
                    f"TimeoutError: a célula passou de {int(timeout)} segundos e foi "
                    "interrompida. Se for um download grande do DATASUS, reduza o "
                    "período/UF ou aumente o tempo limite nas Configurações."
                )
                result.outputs.append(
                    {
                        "output_type": "error",
                        "ename": "TimeoutError",
                        "evalue": result.error_summary,
                        "traceback": [result.error_summary],
                    }
                )
                break
            try:
                msg = self.kc.get_iopub_msg(timeout=1)
            except queue.Empty:
                # Sem mensagem por 1s: o Python pode ter morrido (falta de
                # memória, por exemplo). Sem esta checagem, o aplicativo
                # esperaria o tempo limite inteiro e ainda culparia a demora.
                if not self.alive:
                    result.ok = False
                    result.kernel_morreu = True
                    result.error_summary = MENSAGEM_KERNEL_MORTO
                    result.outputs.append(
                        {
                            "output_type": "error",
                            "ename": "KernelMorto",
                            "evalue": "O Python foi encerrado durante a execução.",
                            "traceback": MENSAGEM_KERNEL_MORTO.splitlines(),
                        }
                    )
                    break
                continue
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue

            mtype = msg["msg_type"]
            content = msg["content"]
            output: dict | None = None

            if mtype == "stream":
                output = {
                    "output_type": "stream",
                    "name": content.get("name", "stdout"),
                    "text": content.get("text", ""),
                }
            elif mtype == "execute_result":
                result.execution_count = content.get("execution_count")
                output = {
                    "output_type": "execute_result",
                    "execution_count": content.get("execution_count"),
                    "data": content.get("data", {}),
                    "metadata": content.get("metadata", {}),
                }
            elif mtype == "display_data":
                output = {
                    "output_type": "display_data",
                    "data": content.get("data", {}),
                    "metadata": content.get("metadata", {}),
                }
            elif mtype == "error":
                traceback = [strip_ansi(line) for line in content.get("traceback", [])]
                result.ok = False
                result.error_summary = "\n".join(traceback) or (
                    f"{content.get('ename')}: {content.get('evalue')}"
                )
                output = {
                    "output_type": "error",
                    "ename": content.get("ename", ""),
                    "evalue": content.get("evalue", ""),
                    "traceback": traceback,
                }
            elif mtype == "execute_input":
                result.execution_count = content.get("execution_count")
            elif mtype == "status" and content.get("execution_state") == "idle":
                break

            if output is not None:
                result.outputs.append(output)
                if on_output is not None:
                    on_output(output)

        return result
