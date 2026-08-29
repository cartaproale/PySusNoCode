"""O que este aplicativo está usando, e o que existe de mais novo lá fora.

Serve a uma pergunta prática de manutenção: *preciso auditar de novo?* Uma
biblioteca que se moveu é o sinal de que os aprendizados do kernel podem ter
envelhecido — foi assim que a PySUS 2.10.4 mudou os grupos do SIA debaixo de
nós, e que o claude-agent-sdk trocou o claude.exe embutido.

Duas famílias de coisa são acompanhadas, e elas envelhecem de formas
diferentes:

- **Bibliotecas**: têm número de versão. Comparamos o instalado com o PyPI.
- **Fontes de dados**: não têm versão. O que envelhece nelas é a *competência*
  mais recente publicada — é isso que diz se o dado andou.

Nada aqui é consultado sozinho: a rede só é tocada quando o usuário pede.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

TEMPO_LIMITE = 12  # segundos por consulta

# Bibliotecas que importam para a análise de dados e para a conversa com a IA.
# PySide6 e pandas ficam de fora de propósito: elas mudam sem afetar o que o
# aplicativo ensina sobre o DATASUS, e só poluiriam a lista.
BIBLIOTECAS = (
    ("pysus", "Acesso ao DATASUS — é ela que define o que dá para baixar"),
    ("claude-agent-sdk", "Conversa pela conta claude.ai (traz o Claude Code)"),
    ("anthropic", "Conversa pela chave da Anthropic"),
    ("openai", "Conversa pela chave da OpenAI"),
)

# Sistemas de onde os dados vêm. O "sisab" é o único que o aplicativo consulta
# diretamente (pelo exemplo da atenção primária); os demais são alcançados
# através da PySUS, e estão aqui para o usuário saber o que precisa liberar e
# se está no ar.
FONTES = (
    {
        "id": "sisab",
        "nome": "SISAB — Relatório de Validação",
        "para": "Atenção primária, por UBS e por equipe",
        "url": ("https://sisab.saude.gov.br/paginas/acessoRestrito/relatorio/"
                "federal/envio/RelValidacao.xhtml"),
    },
    {
        "id": "catalogo",
        "nome": "Catálogo da PySUS",
        "para": "Índice de tudo que a PySUS baixa (fica fora do DATASUS)",
        "url": "https://nbg1.your-objectstorage.com/pysus/public/",
    },
    {
        "id": "demas",
        "nome": "API de dados abertos do Ministério",
        "para": "Atenção primária agregada e outras bases",
        "url": "https://apidadosabertos.saude.gov.br/",
    },
    {
        "id": "opendatasus",
        "nome": "Portal de dados abertos do SUS",
        "para": "Conjuntos publicados pelo Ministério",
        "url": "https://dadosabertos.saude.gov.br/",
    },
)


@dataclass
class Item:
    """Uma linha do quadro: o que usamos, o que existe, e o veredito."""

    nome: str
    descricao: str
    em_uso: str = ""
    disponivel: str = ""
    situacao: str = ""          # "em dia" | "desatualizada" | "?" | "ausente"
    detalhe: str = ""


@dataclass
class Quadro:
    bibliotecas: list[Item] = field(default_factory=list)
    fontes: list[Item] = field(default_factory=list)

    @property
    def desatualizadas(self) -> list[Item]:
        return [i for i in self.bibliotecas if i.situacao == "desatualizada"]


def _numero(texto: str) -> tuple:
    """'2.10.5' → (2, 10, 5). Partes não numéricas viram 0."""
    partes = []
    for pedaco in (texto or "").split("."):
        digitos = "".join(c for c in pedaco if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes) or (0,)


def versao_instalada(pacote: str) -> str:
    import importlib.metadata as md

    try:
        return md.version(pacote)
    except Exception:  # noqa: BLE001
        return ""


def versao_no_pypi(pacote: str) -> tuple[str, str]:
    """(versão mais recente, erro). Consulta a rede."""
    status, corpo, erro = _buscar(f"https://pypi.org/pypi/{pacote}/json")
    if status != 200:
        return "", erro or f"HTTP {status}"
    try:
        return str(json.loads(corpo)["info"]["version"]), ""
    except Exception as e:  # noqa: BLE001
        return "", type(e).__name__


def _buscar(url: str) -> tuple[int, str, str]:
    """GET curto. Devolve (status, corpo, erro). Nada é enviado.

    Usa httpx, e não urllib, DE PROPÓSITO: é o cliente que a PySUS usa, e as
    duas bibliotecas confiam em listas de certificados diferentes. Pelo urllib,
    o catálogo da PySUS aparecia como inalcançável ("certificate has expired")
    enquanto a PySUS o baixava sem queixa — um alarme falso sobre o problema
    mais assustador que o aplicativo pode relatar.
    """
    try:
        import httpx
    except Exception:  # noqa: BLE001
        pedido = urllib.request.Request(url, headers={"User-Agent": "PySusNoCode"})
        try:
            with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as r:
                return r.status, r.read().decode("utf-8", "replace"), ""
        except urllib.error.HTTPError as e:
            return e.code, "", ""
        except Exception as e:  # noqa: BLE001
            return 0, "", type(e).__name__
    try:
        r = httpx.get(url, timeout=TEMPO_LIMITE, follow_redirects=True,
                      headers={"User-Agent": "PySusNoCode"})
        return r.status_code, r.text, ""
    except Exception as e:  # noqa: BLE001
        return 0, "", type(e).__name__


def _fonte_no_ar(url: str) -> tuple[bool, str]:
    """Alcança a fonte? Um 403 de listagem de bucket também é resposta."""
    status, _, erro = _buscar(url)
    if not status:
        return False, erro or "sem resposta"
    return status < 500, f"HTTP {status}"


def competencia_mais_recente_do_sisab() -> str:
    """A competência mais nova oferecida pelo Relatório de Validação.

    É o "número de versão" de uma fonte de dados: diz até quando o dado andou.
    Lida do próprio formulário, sem baixar relatório nenhum.
    """
    import re

    status, html, _ = _buscar(FONTES[0]["url"])
    if status != 200 or not html:
        return ""
    # As competências aparecem como <option value="202608">08/2026</option>
    achados = sorted(set(re.findall(r'value="(20\d{4})"', html)), reverse=True)
    if not achados:
        return ""
    mais_nova = achados[0]
    return f"{mais_nova[4:]}/{mais_nova[:4]}"


def levantar(consultar_rede: bool = True) -> Quadro:
    """Monta o quadro. Sem rede, preenche só o que está instalado aqui."""
    quadro = Quadro()

    for pacote, descricao in BIBLIOTECAS:
        item = Item(nome=pacote, descricao=descricao)
        item.em_uso = versao_instalada(pacote)
        if not item.em_uso:
            item.situacao = "ausente"
            item.detalhe = "não instalada neste computador"
        elif consultar_rede:
            item.disponivel, erro = versao_no_pypi(pacote)
            if not item.disponivel:
                item.situacao = "?"
                item.detalhe = f"não consegui consultar o PyPI ({erro})"
            elif _numero(item.disponivel) > _numero(item.em_uso):
                item.situacao = "desatualizada"
            else:
                item.situacao = "em dia"
        else:
            item.situacao = "?"
        quadro.bibliotecas.append(item)

    for fonte in FONTES:
        item = Item(nome=fonte["nome"], descricao=fonte["para"])
        item.detalhe = fonte["url"]
        if not consultar_rede:
            item.situacao = "?"
        else:
            no_ar, como = _fonte_no_ar(fonte["url"])
            item.situacao = "em dia" if no_ar else "ausente"
            item.em_uso = como
            if fonte["id"] == "sisab" and no_ar:
                comp = competencia_mais_recente_do_sisab()
                if comp:
                    item.disponivel = f"até {comp}"
        quadro.fontes.append(item)

    return quadro
