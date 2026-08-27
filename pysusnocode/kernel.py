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


# Erros que não vêm do código escrito, e sim do ambiente. Pedir correção à IA
# nesses casos só gasta as tentativas: o código está certo, o problema está
# fora dele. Cada entrada exige que TODAS as marcas de "sempre" apareçam e ao
# menos uma das de "alguma", para não confundir com erro de verdade.
# Endereços que a PySUS precisa alcançar. Levantados no código da própria
# biblioteca (pysus.api.types.S3_ENDPOINT e api/ftp/client.py), não supostos:
# antes de baixar qualquer arquivo do DATASUS, ela consulta um catálogo
# hospedado num armazenamento externo — e é justamente esse que as redes
# institucionais costumam bloquear, por cair na categoria "cloud storage".
ENDERECOS_NECESSARIOS = (
    ("*.your-objectstorage.com", "catálogo de arquivos da PySUS (HTTPS)"),
    ("ftp.datasus.gov.br", "arquivos do DATASUS (FTP, porta 21)"),
    ("apidadosabertos.saude.gov.br", "atenção primária e SISAB (HTTPS)"),
    ("dadosabertos.saude.gov.br", "portal de dados abertos do Ministério (HTTPS)"),
    ("pypi.org e files.pythonhosted.org", "só durante a instalação do programa"),
)

TEXTO_PARA_TI = (
    "— — — texto para abrir o chamado na TI — — —\n\n"
    "Solicito a liberação, no firewall, proxy e filtro de conteúdo, do domínio "
    "*.your-objectstorage.com por HTTPS (porta 443).\n\n"
    "A biblioteca pública PySUS, usada para acessar dados do DATASUS, consulta "
    "seu catálogo de arquivos em "
    "https://nbg1.your-objectstorage.com/pysus/public/ antes de qualquer "
    "download. A conexão TCP na porta 443 chega a ser estabelecida, mas a "
    "negociação TLS não se completa quando o acesso passa pela rede da "
    "instituição; pelo 4G o mesmo endereço funciona.\n\n"
    "Três observações que costumam ser necessárias:\n\n"
    "1. A regra deve ser por nome de domínio (FQDN), não por IP: é uma "
    "infraestrutura em nuvem e os endereços mudam.\n"
    "2. Verificar se a inspeção de TLS está interferindo na conexão.\n"
    "3. O proxy precisa preservar requisições HTTP Range e permitir respostas "
    "206 Partial Content com Content-Range — o catálogo é lido em pedaços. "
    "Sem isso, uma consulta simples passa a baixar arquivos de até 128 MB.\n\n"
    "Também são necessários: ftp.datasus.gov.br (FTP, porta 21), "
    "apidadosabertos.saude.gov.br e dadosabertos.saude.gov.br (HTTPS).\n"
    "— — — fim do texto — — —"
)

ERROS_DE_AMBIENTE = (
    {
        "sempre": ("duckdb",),
        "alguma": (
            "já está sendo usado por outro processo",
            # a mesma frase sem acentos: dependendo da página de código do
            # console, o Windows devolve o texto assim
            "ja esta sendo usado por outro processo",
            "being used by another process",
            "could not set lock on file",
            "file is already open",
        ),
        "explicacao": (
            "O catálogo de dados do DATASUS está aberto por outro programa.\n\n"
            "A biblioteca PySUS guarda o índice de todas as bases num único "
            "arquivo, e ele não pode ser usado por dois programas ao mesmo "
            "tempo. Quase sempre há outra janela do PySusNoCode aberta, ou um "
            "notebook rodando fora daqui.\n\n"
            "Feche a outra janela e execute esta célula de novo. Não é preciso "
            "mudar o código: ele está correto."
        ),
    },
    # Inspeção de TLS vem ANTES do tempo esgotado: quando o equipamento da rede
    # troca o certificado, o sintoma é de certificado e não de demora, e a
    # orientação para a TI é outra.
    {
        "sempre": ("pysus",),
        "alguma": (
            "certificate_verify_failed",
            "sslcertverificationerror",
            "unable to get local issuer certificate",
            "self-signed certificate",
            "self signed certificate",
            "ssl: certificate",
        ),
        "explicacao": (
            "A rede está inspecionando o tráfego seguro e o Python recusou o "
            "certificado.\n\n"
            "Não é erro do código nem do seu computador. Em redes de "
            "prefeituras, hospitais e empresas é comum um equipamento abrir o "
            "tráfego HTTPS e reemitir os certificados. Navegadores aceitam "
            "isso porque confiam no certificado da instituição; o Python, que "
            "tem a própria lista de certificados, não aceita.\n\n"
            f"{TEXTO_PARA_TI}"
        ),
    },
    {
        "sempre": ("pysus",),
        "alguma": (
            "connecttimeout",
            "connecterror",
            "readtimeout",
            "connect timeout",
            "timed out",
            "max retries exceeded",
            "failed to establish a new connection",
        ),
        "explicacao": (
            "A rede bloqueou o endereço de onde a PySUS busca o catálogo.\n\n"
            "A mensagem fala em tempo esgotado, o que faz parecer internet "
            "lenta — mas quase sempre não é. Em redes controladas o "
            "equipamento simplesmente não responde ao endereço bloqueado, e a "
            "espera acaba em tempo esgotado.\n\n"
            "Repare que liberar só os endereços do DATASUS não basta: antes de "
            "baixar qualquer arquivo, a PySUS consulta um catálogo hospedado "
            "em outro serviço.\n\n"
            "Duas saídas:\n\n"
            "1. Peça a liberação à TI, com o texto pronto abaixo.\n\n"
            "2. Enquanto isso, use uma rede fora do controle da instituição — "
            "o 4G do seu celular, por exemplo. Atenção: não basta conectar no "
            "Wi-Fi do celular. Com o cabo de rede ligado, o Windows continua "
            "mandando tudo pelo cabo. É preciso desconectar o cabo (ou "
            "desativar o adaptador Ethernet nas configurações do Windows) para "
            "que o tráfego passe pelo celular.\n\n"
            f"{TEXTO_PARA_TI}"
        ),
    },
)


def erro_de_ambiente(texto: str) -> str | None:
    """Reconhece erros que não são do código e explica o que fazer.

    Devolve a explicação em português, ou None se o erro for mesmo do código.
    """
    baixo = (texto or "").lower()
    for caso in ERROS_DE_AMBIENTE:
        if all(marca in baixo for marca in caso["sempre"]) and any(
            marca in baixo for marca in caso["alguma"]
        ):
            return caso["explicacao"]
    return None


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
            # NÃO chamamos pysus.disable_progress_bars() aqui. A função existe
            # desde a 2.10 e promete exatamente o que queríamos — tirar as
            # barras de download, que viram uma parede de lixo na saída —, mas
            # foi testada na 2.10.3 e não tem efeito nenhum: as barras
            # continuam saindo em stderr. Chamá-la custaria importar a pysus a
            # cada início de kernel (mais de um segundo) sem ganho algum.
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
