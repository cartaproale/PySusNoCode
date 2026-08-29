"""Gera TERCEIROS.md a partir das wheels que vao dentro do instalador.

Por que existe: o PySusNoCode e MIT, mas o instalador completo carrega 122
bibliotecas de terceiros, e algumas sao copyleft — a PySUS e GPLv3, o pyreaddbc
e AGPL-3.0, o PySide6 e LGPL. Distribuir esse conjunto exige dizer o que ele
contem e sob que licenca. Ate 29/08/2026 nao diziamos nada.

Por que gerado, e nao escrito a mao: lista de dependencia escrita a mao envelhece
em silencio, como envelheceu a contagem de exemplos na tela de abertura. Esta sai
dos proprios arquivos .whl a cada compilacao.

Uso:
    python installer/gerar_terceiros.py
    python installer/gerar_terceiros.py --conferir   # so avisa se estiver velho
"""

from __future__ import annotations

import re
import sys
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WHEELS = RAIZ / "installer" / "vendor" / "wheels"
DESTINO = RAIZ / "TERCEIROS.md"

# Licencas que impoem obrigacao de reciprocidade. Nao impedem a distribuicao,
# mas exigem que o usuario saiba que estao ali e onde achar o codigo.
COPYLEFT = re.compile(r"\bA?GPL|LGPL|MPL|EPL|CDDL", re.I)

# O que dizer sobre cada familia, em portugues, para quem nao e advogado.
EXPLICACAO = {
    "AGPL": "copyleft forte, com clausula de rede",
    "LGPL": "copyleft de biblioteca: usar nao contamina o aplicativo",
    "GPL": "copyleft forte",
    "MPL": "copyleft fraco, por arquivo",
}


def _campo(texto: str, nome: str) -> str:
    m = re.search(rf"^{nome}:\s*(.+)$", texto, re.M)
    return m.group(1).strip() if m else ""


def _licenca(texto: str) -> str:
    """A licenca declarada, preferindo a forma moderna e curta."""
    for campo in ("License-Expression", "License"):
        v = _campo(texto, campo)
        # Alguns pacotes despejam a licenca INTEIRA no campo License.
        if v and len(v) <= 60 and "\n" not in v:
            return v
    classificadores = re.findall(r"^Classifier: License :: (.+)$", texto, re.M)
    if classificadores:
        return classificadores[-1].replace("OSI Approved :: ", "").strip()
    return "não declarada"


# Repositorios conferidos a mao (HTTP 200 em 29/08/2026) para os componentes
# copyleft que NAO declaram endereco nenhum nos metadados nem no PyPI. Sao
# justamente aqueles cuja licenca obriga a dizer onde esta o codigo.
REPOSITORIOS = {
    "pysus": "https://github.com/AlertaDengue/PySUS",
    "pyreaddbc": "https://github.com/AlertaDengue/PyReadDBC",
    "unidecode": "https://github.com/avian2/unidecode",
}


def _endereco(texto: str, nome: str) -> str:
    """Onde achar o codigo. Nunca devolve vazio para nada que esteja no PyPI."""
    url = _campo(texto, "Home-page")
    if url and url.upper() != "UNKNOWN":
        return url
    for linha in re.findall(r"^Project-URL:\s*(.+)$", texto, re.M):
        rotulo, _, valor = linha.partition(",")
        if rotulo.strip().lower() in ("homepage", "source", "repository",
                                      "source code"):
            return valor.strip()
    if nome.lower() in REPOSITORIOS:
        return REPOSITORIOS[nome.lower()]
    # A pagina do PyPI sempre existe e serve o sdist — o codigo-fonte.
    return f"https://pypi.org/project/{nome}/" if nome else ""


def levantar() -> list[dict]:
    if not WHEELS.exists():
        raise SystemExit(
            f"pasta de wheels ausente: {WHEELS}\n"
            "Rode antes: pwsh installer\\baixar_wheels.ps1")
    itens = []
    for caminho in sorted(WHEELS.glob("*.whl")):
        with zipfile.ZipFile(caminho) as z:
            nomes = z.namelist()
            meta = next((n for n in nomes if n.endswith(".dist-info/METADATA")), "")
            texto = z.read(meta).decode("utf-8", errors="replace") if meta else ""
            tem_texto_da_licenca = any(
                "LICENSE" in n.upper() or "COPYING" in n.upper() for n in nomes)
        itens.append({
            "nome": _campo(texto, "Name") or caminho.name.split("-")[0],
            "versao": _campo(texto, "Version") or "?",
            "licenca": _licenca(texto),
            "url": _endereco(texto, _campo(texto, "Name")
                             or caminho.name.split("-")[0]),
            "texto_embarcado": tem_texto_da_licenca,
            "arquivo": caminho.name,
        })
    return sorted(itens, key=lambda i: i["nome"].lower())


def montar(itens: list[dict]) -> str:
    reciprocas = [i for i in itens if COPYLEFT.search(i["licenca"])]

    def familia(licenca: str) -> str:
        for chave in ("AGPL", "LGPL", "GPL", "MPL"):
            if re.search(rf"\b{chave}", licenca, re.I):
                return chave
        return ""

    linhas = [
        "# Componentes de terceiros",
        "",
        "O **PySusNoCode** é distribuído sob a licença MIT (veja `LICENSE`).",
        "",
        "O instalador completo embarca as bibliotecas listadas abaixo, para que a",
        "instalação funcione em redes que bloqueiam o pypi.org — o caso de boa parte",
        "das prefeituras e unidades de saúde. Cada uma continua sob a licença do seu",
        "próprio autor, e o texto integral de cada licença viaja dentro do respectivo",
        "arquivo `.whl`, na pasta `vendor/wheels` da instalação.",
        "",
        f"Lista gerada automaticamente por `installer/gerar_terceiros.py` em "
        f"{date.today().strftime('%d/%m/%Y')}, a partir dos "
        f"{len(itens)} arquivos que vão no instalador.",
        "",
        "## As que pedem atenção",
        "",
        "Estas têm licenças recíprocas (*copyleft*). Nenhuma delas impede a",
        "distribuição do PySusNoCode, e nenhuma obriga a mudar a licença do nosso",
        "código — mas todas exigem que se diga que estão aqui e onde encontrar o",
        "código-fonte delas.",
        "",
        "| Biblioteca | Versão | Licença | O que isso significa | Código-fonte |",
        "|---|---|---|---|---|",
    ]
    for i in reciprocas:
        expl = EXPLICACAO.get(familia(i["licenca"]), "")
        alvo = i["url"]
        rotulo = "pypi.org" if "pypi.org" in alvo else alvo.split("//")[-1][:38]
        url = f"[{rotulo}]({alvo})" if alvo else "—"
        linhas.append(f"| `{i['nome']}` | {i['versao']} | {i['licenca']} | "
                      f"{expl} | {url} |")

    linhas += [
        "",
        "Duas observações sobre a lista acima:",
        "",
        "- **O PySusNoCode não se liga à PySUS.** O programa não a importa em momento",
        "  algum; quem a executa é o notebook que você gera, num processo separado.",
        "  O instalador apenas a transporta.",
        "- **PySide6 e shiboken6 são usadas pelo programa**, sob a LGPL. É para isso",
        "  que a LGPL existe: um aplicativo de outra licença pode usá-las, desde que",
        "  o usuário possa substituir a biblioteca — e pode, os arquivos estão soltos",
        "  em `vendor/` e na pasta de instalação.",
        "",
        "## Todas as bibliotecas embarcadas",
        "",
        "| Biblioteca | Versão | Licença |",
        "|---|---|---|",
    ]
    for i in itens:
        linhas.append(f"| `{i['nome']}` | {i['versao']} | {i['licenca']} |")

    sem_texto = [i["nome"] for i in itens if not i["texto_embarcado"]]
    linhas += [
        "",
        "---",
        "",
        f"{len(itens)} bibliotecas. "
        f"{len(itens) - len(sem_texto)} trazem o texto da licença dentro do "
        f"próprio arquivo `.whl`.",
    ]
    if sem_texto:
        linhas += [
            "",
            f"Sem arquivo de licença embarcado ({len(sem_texto)}): "
            + ", ".join(f"`{n}`" for n in sem_texto)
            + ". Para essas, a licença declarada nos metadados é a da tabela acima.",
        ]
    linhas += [
        "",
        "Se você precisar do código-fonte de qualquer componente copyleft e não",
        "conseguir obtê-lo no endereço indicado, abra uma questão em",
        "<https://github.com/cartaproale/PySusNoCode/issues>.",
        "",
    ]
    return "\n".join(linhas)


def main() -> int:
    itens = levantar()
    texto = montar(itens)
    if "--conferir" in sys.argv:
        atual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        # A data muda todo dia; comparamos o resto.
        def sem_data(t): return re.sub(r"em \d{2}/\d{2}/\d{4}", "em DATA", t)
        if sem_data(atual) != sem_data(texto):
            print("TERCEIROS.md esta desatualizado. Rode:")
            print("   python installer/gerar_terceiros.py")
            return 1
        print("TERCEIROS.md esta em dia.")
        return 0

    DESTINO.write_text(texto, encoding="utf-8")
    reciprocas = [i for i in itens if COPYLEFT.search(i["licenca"])]
    print(f"TERCEIROS.md gerado: {len(itens)} bibliotecas, "
          f"{len(reciprocas)} com licenca reciproca")
    for i in reciprocas:
        print(f"   {i['nome']:22} {i['licenca']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
