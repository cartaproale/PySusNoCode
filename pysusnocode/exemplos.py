"""Catálogo de notebooks de exemplo, prontos e validados.

Os exemplos moram num repositório à parte
(github.com/cartaproale/PySusNoCode-Exemplos), onde cada um é executado do
início ao fim com dados reais antes de ser publicado. O aplicativo os oferece
de duas formas:

- **do instalador**: uma cópia vai dentro do programa, e por isso a lista abre
  na hora e funciona sem internet — o caso das unidades de saúde e prefeituras,
  onde a rede é controlada;
- **do GitHub**: quando há internet, buscamos a versão mais recente, porque os
  exemplos são revalidados todo mês e podem ter sido corrigidos depois que o
  instalador foi gerado.

A preferência é sempre pelo GitHub, com queda para a cópia local. O usuário é
informado de qual das duas veio o que ele está vendo.
"""

from __future__ import annotations

import json
from pathlib import Path

REPOSITORIO = "cartaproale/PySusNoCode-Exemplos"
RAMO = "main"
BASE_CRUA = f"https://raw.githubusercontent.com/{REPOSITORIO}/{RAMO}"
URL_CATALOGO = f"{BASE_CRUA}/exemplos.json"
PAGINA = f"https://github.com/{REPOSITORIO}"

ORIGEM_GITHUB = "github"
ORIGEM_LOCAL = "instalador"

# Tempos curtos: a lista precisa abrir rápido, e se a rede estiver bloqueada é
# melhor mostrar a cópia local do que deixar o usuário esperando.
ESPERA_CATALOGO = 6
ESPERA_NOTEBOOK = 45


def pasta_local() -> Path:
    """Onde está a cópia dos exemplos que veio com o programa.

    Três lugares, nesta ordem:

    - instalado, o pacote fica em ``{app}\\app\\pysusnocode`` e os exemplos em
      ``{app}\\exemplos``;
    - rodando do código-fonte, a cópia que ``installer/copiar_exemplos.ps1``
      preparou;
    - ainda no código-fonte, o próprio repositório de exemplos ao lado, para
      que o desenvolvimento use exatamente os mesmos arquivos.
    """
    pacote = Path(__file__).resolve().parent
    projeto = pacote.parent                    # PySusNoCodeForWindows (ou {app}\app)
    candidatos = [
        projeto.parent / "exemplos",                    # instalado
        projeto / "installer" / "exemplos",             # código-fonte, já copiado
        projeto.parent / "PySusNoCode-Exemplos",        # repositório vizinho
    ]
    for caminho in candidatos:
        if (caminho / "exemplos.json").exists():
            return caminho
    return candidatos[0]


def _baixar(url: str, espera: int) -> bytes:
    from urllib.request import Request, urlopen

    pedido = Request(url, headers={"User-Agent": "PySusNoCode"})
    with urlopen(pedido, timeout=espera) as resposta:  # noqa: S310
        return resposta.read()


# Preenchido a cada carga do catálogo: {"data", "funcionando", "total",
# "versao_pysus"}. É o resumo do VALIDACAO.md que o gerar_catalogo.py embute
# no exemplos.json — a interface o mostra para o usuário saber CONTRA O QUÊ
# cada exemplo foi validado, e quando.
RESUMO_VALIDACAO: dict = {}


def carregar_catalogo(preferir_github: bool = True) -> tuple[list[dict], str, str]:
    """Devolve (exemplos, origem, aviso).

    Nunca levanta exceção: sem rede e sem cópia local, devolve lista vazia com
    um aviso em português explicando o que aconteceu.
    """
    problema = ""
    if preferir_github:
        try:
            dados = json.loads(_baixar(URL_CATALOGO, ESPERA_CATALOGO).decode("utf-8"))
            RESUMO_VALIDACAO.clear()
            RESUMO_VALIDACAO.update(dados.get("validacao", {}))
            return dados.get("exemplos", []), ORIGEM_GITHUB, ""
        except Exception as erro:  # noqa: BLE001
            problema = str(erro)

    arquivo = pasta_local() / "exemplos.json"
    if arquivo.exists():
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
            aviso = ""
            if problema:
                aviso = ("Não consegui falar com o GitHub agora, então esta é a "
                         "lista que veio no instalador.")
            RESUMO_VALIDACAO.clear()
            RESUMO_VALIDACAO.update(dados.get("validacao", {}))
            return dados.get("exemplos", []), ORIGEM_LOCAL, aviso
        except Exception:  # noqa: BLE001
            pass

    return [], ORIGEM_LOCAL, (
        "Não encontrei a lista de exemplos nem no GitHub nem nesta instalação. "
        f"Você pode vê-los pelo navegador em {PAGINA}."
    )


def obter_notebook(arquivo: str, preferir_github: bool = True) -> tuple[Path, str]:
    """Traz o .ipynb do exemplo e devolve (caminho, origem).

    O caminho pode ser temporário (quando vem do GitHub) ou o próprio arquivo
    da instalação. Levanta a exceção original quando não consegue de nenhum
    dos dois jeitos, para que a janela mostre o motivo ao usuário.
    """
    erro_remoto: Exception | None = None
    if preferir_github:
        try:
            conteudo = _baixar(f"{BASE_CRUA}/{arquivo}", ESPERA_NOTEBOOK)
            json.loads(conteudo.decode("utf-8"))     # confere que é um notebook
            import tempfile

            destino = Path(tempfile.gettempdir()) / "PySusNoCode-exemplos"
            destino.mkdir(parents=True, exist_ok=True)
            alvo = destino / Path(arquivo).name
            alvo.write_bytes(conteudo)
            return alvo, ORIGEM_GITHUB
        except Exception as erro:  # noqa: BLE001
            erro_remoto = erro

    local = pasta_local() / arquivo
    if local.exists():
        return local, ORIGEM_LOCAL

    raise erro_remoto or FileNotFoundError(
        f"O exemplo {arquivo} não está nesta instalação e não consegui baixá-lo."
    )


def agrupar(exemplos: list[dict]) -> list[tuple[str, list[dict]]]:
    """Organiza para exibição, preservando a ordem que veio do catálogo."""
    grupos: dict[str, list[dict]] = {}
    for item in exemplos:
        grupos.setdefault(item.get("grupo") or "Outros", []).append(item)
    return list(grupos.items())
