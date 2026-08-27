"""Verificação de novas versões do PySusNoCode.

Consulta a última Release publicada no GitHub e compara com a versão em uso.
Nada é baixado nem instalado automaticamente: quando há novidade, o aplicativo
apenas avisa e oferece abrir a página de download no navegador.

A consulta não envia nenhum dado do usuário — é um pedido público de leitura,
e pode ser desligada nas Configurações.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date

from . import __version__

REPO = "cartaproale/PySusNoCode"
API_ULTIMA_RELEASE = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA_RELEASE = f"https://github.com/{REPO}/releases/latest"
DOWNLOAD_DIRETO = (
    f"https://github.com/{REPO}/releases/latest/download/PySusNoCode-Setup.exe"
)
TEMPO_LIMITE = 8  # segundos


@dataclass
class Atualizacao:
    versao: str
    notas: str
    pagina: str = PAGINA_RELEASE
    download: str = DOWNLOAD_DIRETO


def numero_versao(texto: str) -> tuple[int, ...]:
    """'v1.4.1' → (1, 4, 1). Partes não numéricas viram 0."""
    limpo = (texto or "").strip().lstrip("vV").split("-")[0].split("+")[0]
    partes: list[int] = []
    for pedaco in limpo.split("."):
        digitos = "".join(c for c in pedaco if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes) or (0,)


def e_mais_nova(candidata: str, atual: str = __version__) -> bool:
    a, b = numero_versao(candidata), numero_versao(atual)
    tamanho = max(len(a), len(b))
    a += (0,) * (tamanho - len(a))
    b += (0,) * (tamanho - len(b))
    return a > b


class FalhaNaConsulta(OSError):
    """Não deu para consultar — com a explicação do porquê, em português.

    Até a versão 1.8.12 qualquer falha aqui virava "verifique sua conexão com
    a internet". Numa prefeitura isso mandava o usuário procurar um problema
    que não existia: a internet estava boa, e o que havia era o bloqueio do
    endereço da API. Agora a mensagem diz o que realmente aconteceu.
    """

    def __init__(self, explicacao: str) -> None:
        super().__init__(explicacao)
        self.explicacao = explicacao


def _proxy_do_sistema() -> str:
    """Proxy configurado no Windows, se houver.

    Importa porque o Python usa essa configuração mesmo quando o computador
    está noutra rede. Num notebook de trabalho levado para o 4G do celular, o
    proxy da instituição continua sendo procurado — e não responde.
    """
    try:
        proxies = urllib.request.getproxies()
    except Exception:  # noqa: BLE001
        return ""
    for chave in ("https", "http"):
        if proxies.get(chave):
            return proxies[chave]
    return ""


def _consultar_api() -> tuple[str, str]:
    """Pergunta à API do GitHub. Devolve (tag, notas)."""
    pedido = urllib.request.Request(
        API_ULTIMA_RELEASE,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"PySusNoCode/{__version__}",
        },
    )
    with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))
    notas = str(dados.get("body") or "").strip()
    if len(notas) > 600:
        notas = notas[:600].rsplit(" ", 1)[0] + "…"
    return str(dados.get("tag_name") or ""), notas


def _consultar_pelo_redirecionamento() -> tuple[str, str]:
    """Descobre a versão sem usar a API, só pelo endereço de download.

    A página /releases/latest redireciona para /releases/tag/vX.Y.Z, então o
    número da versão está no próprio endereço de destino. Isso usa o mesmo
    host de onde o instalador é baixado (github.com), e não a API
    (api.github.com), que é um endereço diferente e costuma ser bloqueado
    separadamente pelos filtros de conteúdo.
    """
    class _SoOPrimeiroRedirecionamento(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise _Destino(newurl)

    class _Destino(Exception):
        def __init__(self, url: str) -> None:
            self.url = url

    abridor = urllib.request.build_opener(_SoOPrimeiroRedirecionamento)
    pedido = urllib.request.Request(
        PAGINA_RELEASE, headers={"User-Agent": f"PySusNoCode/{__version__}"}
    )
    destino = ""
    try:
        with abridor.open(pedido, timeout=TEMPO_LIMITE) as resposta:
            destino = resposta.geturl()
    except _Destino as parada:
        destino = parada.url

    marca = "/releases/tag/"
    if marca not in destino:
        raise FalhaNaConsulta(
            "O GitHub respondeu, mas não informou qual é a última versão."
        )
    return destino.split(marca, 1)[1].strip("/"), ""


def verificar() -> Atualizacao | None:
    """Devolve a atualização disponível, ou None se já estiver em dia.

    Levanta FalhaNaConsulta, com explicação em português, quando não consegue
    consultar. Tenta primeiro a API do GitHub e, se ela falhar, o
    redirecionamento da página de versões — que passa por outro endereço e
    costuma funcionar mesmo onde a API está bloqueada.
    """
    tag = notas = ""
    erro_api = ""
    try:
        tag, notas = _consultar_api()
    except urllib.error.HTTPError as erro:
        if erro.code == 403:
            erro_api = (
                "o GitHub recusou a consulta por excesso de pedidos (403). Em "
                "rede de instituição, muitos computadores saem pelo mesmo "
                "endereço e o limite da API é compartilhado entre todos"
            )
        else:
            erro_api = f"o GitHub respondeu com erro {erro.code}"
    except Exception as erro:  # noqa: BLE001
        erro_api = f"{type(erro).__name__}"

    if not tag:
        try:
            tag, notas = _consultar_pelo_redirecionamento()
        except Exception as erro:  # noqa: BLE001
            # Quando já temos uma frase em português, ela diz mais do que o
            # nome da classe da exceção.
            motivo = (
                erro.explicacao
                if isinstance(erro, FalhaNaConsulta)
                else type(erro).__name__
            )
            proxy = _proxy_do_sistema()
            detalhe = (
                f"\n\nHá um proxy configurado neste computador ({proxy}). O "
                "Python usa essa configuração mesmo quando você troca de rede "
                "— então, num notebook levado para o 4G do celular, ele "
                "continua tentando falar com o proxy da instituição."
                if proxy else ""
            )
            raise FalhaNaConsulta(
                "Não consegui perguntar ao GitHub qual é a última versão.\n\n"
                f"Pela API (api.github.com): {erro_api or 'falhou'}.\n"
                f"Pela página de versões (github.com): {motivo}."
                f"{detalhe}\n\n"
                "Em redes de prefeituras, hospitais e empresas é comum o "
                "endereço api.github.com estar bloqueado mesmo quando "
                "github.com funciona — são endereços diferentes, liberados "
                "separadamente.\n\n"
                "Você pode baixar a versão mais recente direto pela página de "
                "download, que usa só o github.com:\n"
                f"{PAGINA_RELEASE}"
            ) from erro

    if not tag or not e_mais_nova(tag):
        return None
    return Atualizacao(versao=tag.lstrip("vV"), notas=notas)


def marca_de_hoje() -> str:
    """Data da última consulta, guardada apenas como registro.

    Até a versão 1.8.5 esta data também servia de trava: o aplicativo
    verificava uma vez por dia. Deixou de travar — agora a consulta acontece a
    cada abertura, para que uma correção importante não demore um dia inteiro
    para chegar a quem já tem o programa instalado.
    """
    return str(date.today())
