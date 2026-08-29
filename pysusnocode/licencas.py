"""O que este programa usa, e sob que licença.

O PySusNoCode é MIT, mas o instalador transporta 122 bibliotecas de outros
autores — e sete delas têm licença recíproca: a PySUS é GPLv3, o pyreaddbc é
AGPL-3.0, o PySide6 é LGPL. Nenhuma impede a distribuição; todas pedem que se
diga que estão aqui.

Este módulo existe para que essa informação chegue a quem instala, e não só a
quem lê o repositório. Ele lê os arquivos que o instalador deixa ao lado do
programa (`LICENSE` e `TERCEIROS.md`) e, quando eles não estão lá — instalação
antiga, ou execução a partir do código-fonte —, ainda assim diz o essencial.
"""

from __future__ import annotations

from pathlib import Path

# O essencial, que vale mesmo sem os arquivos por perto. Conferido em
# 29/08/2026 nas próprias wheels que vão no instalador.
RECIPROCAS = [
    ("pysus", "GPL-3.0", "https://github.com/AlertaDengue/PySUS"),
    ("pyreaddbc", "AGPL-3.0", "https://github.com/AlertaDengue/PyReadDBC"),
    ("PySide6-Essentials", "LGPL-3.0", "https://pyside.org"),
    ("shiboken6", "LGPL-3.0", "https://pyside.org"),
    ("Unidecode", "GPL", "https://github.com/avian2/unidecode"),
    ("certifi", "MPL-2.0", "https://github.com/certifi/python-certifi"),
    ("tqdm", "MPL-2.0 e MIT", "https://tqdm.github.io"),
]

ARQUIVOS = ("LICENSE", "TERCEIROS.md")


def onde_estao() -> Path | None:
    """A pasta com LICENSE e TERCEIROS.md, ou None se não houver.

    Instalado, o pacote fica em ``{app}\\app\\pysusnocode`` e os arquivos em
    ``{app}``. Rodando do código-fonte, ambos ficam na raiz do repositório.
    """
    pacote = Path(__file__).resolve().parent
    projeto = pacote.parent
    for candidata in (projeto, projeto.parent):
        if all((candidata / nome).exists() for nome in ARQUIVOS):
            return candidata
    return None


def resumo() -> str:
    """Texto curto para a janela, em português e sem jargão jurídico."""
    linhas = [
        "O PySusNoCode é software livre, sob a licença MIT.",
        "",
        "Ele usa e distribui bibliotecas escritas por outras pessoas. A maioria",
        "tem licença permissiva (MIT, BSD, Apache). Sete têm licença recíproca,",
        "que permite usar e redistribuir livremente, mas pede que se diga que",
        "elas estão aqui e onde encontrar o código delas:",
        "",
    ]
    for nome, licenca, url in RECIPROCAS:
        linhas.append(f"   • {nome} — {licenca}")
        linhas.append(f"       {url}")
    linhas += [
        "",
        "Duas observações que costumam ser perguntadas:",
        "",
        "• O PySusNoCode não se liga à PySUS. O programa não a importa; quem a",
        "  executa é o notebook que você gera, num processo separado.",
        "• PySide6 é usada pelo programa, sob a LGPL — que existe exatamente",
        "  para isso, desde que você possa substituir a biblioteca. Você pode:",
        "  os arquivos ficam soltos na pasta da instalação.",
    ]
    pasta = onde_estao()
    if pasta is not None:
        linhas += [
            "",
            "A lista completa das 122 bibliotecas, com versão e licença de cada",
            "uma, está em TERCEIROS.md. O texto integral de cada licença viaja",
            "dentro do próprio arquivo .whl, em vendor/wheels.",
        ]
    else:
        linhas += [
            "",
            "A lista completa está em TERCEIROS.md, no repositório:",
            "https://github.com/cartaproale/PySusNoCode",
        ]
    return "\n".join(linhas)
