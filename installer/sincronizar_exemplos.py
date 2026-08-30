"""Copia os notebooks do repositório de exemplos para dentro do instalador.

O PySusNoCode.iss leva a pasta exemplos inteira — o que estiver nela na hora do build.
Não havia nenhum passo que garantisse que essa pasta refletia o repositório de
exemplos, e ela já tinha derivado: quatro notebooks corrigidos em 30/08/2026
continuavam ali na versão antiga, prontos para serem instalados no computador de
alguém como se fossem os bons.

Uso:
    python installer/sincronizar_exemplos.py --conferir   # só acusa a deriva
    python installer/sincronizar_exemplos.py              # copia
"""

from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "installer" / "exemplos"
PADRAO_FONTE = RAIZ.parent / "PySusNoCode-Exemplos"


def fonte() -> Path:
    for argumento in sys.argv[1:]:
        if not argumento.startswith("--"):
            caminho = Path(argumento).expanduser().resolve()
            if not caminho.is_dir():
                raise SystemExit(f"não é uma pasta: {caminho}")
            return caminho
    if not PADRAO_FONTE.is_dir():
        raise SystemExit(
            f"não achei o repositório de exemplos em {PADRAO_FONTE}. "
            "Passe o caminho como argumento."
        )
    return PADRAO_FONTE


def arquivos(raiz: Path) -> dict[str, Path]:
    achados = {}
    for p in raiz.rglob("*.ipynb"):
        if "_ferramentas" in p.parts or ".ipynb_checkpoints" in p.parts:
            continue
        achados[p.relative_to(raiz).as_posix()] = p
    catalogo = raiz / "exemplos.json"
    if catalogo.is_file():
        achados["exemplos.json"] = catalogo
    return achados


def main() -> int:
    de = fonte()
    so_conferir = "--conferir" in sys.argv[1:]
    origem = arquivos(de)
    if not origem:
        raise SystemExit(f"nenhum notebook em {de}")
    atual = arquivos(DESTINO)

    mudados = [r for r, p in origem.items()
               if r not in atual or not filecmp.cmp(p, atual[r], shallow=False)]
    sobrando = sorted(set(atual) - set(origem))

    print(f"fonte:   {de}")
    print(f"destino: {DESTINO}")
    print(f"{len(origem)} arquivos na fonte, {len(mudados)} diferentes, "
          f"{len(sobrando)} sobrando no destino\n")
    for r in sorted(mudados):
        print(f"  difere:  {r}")
    for r in sobrando:
        print(f"  sobra:   {r}")

    if not mudados and not sobrando:
        print("em dia.")
        return 0

    if so_conferir:
        print("\nA pasta do instalador NÃO reflete o repositório de exemplos. "
              "Rode sem --conferir antes de gerar o instalador.")
        return 1

    for r in mudados:
        alvo = DESTINO / r
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem[r], alvo)
    for r in sobrando:
        (DESTINO / r).unlink()
    print(f"\n{len(mudados)} copiados, {len(sobrando)} removidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
