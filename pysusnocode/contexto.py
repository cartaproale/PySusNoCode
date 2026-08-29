"""O que a IA precisa saber sobre o notebook que está aberto.

Até a 1.8.23 ela não sabia nada: o prompt levava só as lições, e o conteúdo do
notebook nunca era enviado. O efeito aparecia na conversa — quando o usuário
pedia "altere a célula que define o município", a IA respondia que não conseguia
enxergar a célula e pedia para o usuário colar o texto. Não era modéstia: era
verdade literal.

Este módulo monta o retrato do notebook que vai junto do pedido. Duas decisões
que valem explicação:

- **só o código-fonte, sem as saídas.** As saídas são o que há de mais volumoso
  num notebook (uma tabela de mil linhas, uma imagem em base64) e o que menos
  ajuda a decidir o que editar. O resultado da execução já chega por outro
  caminho, as `exec_notes`.
- **numeração igual à da tela.** A IA precisa poder dizer "célula 4" e o usuário
  achar a célula 4. Por isso contamos a partir de 1, contando markdown junto,
  exatamente como o painel mostra.
"""

from __future__ import annotations

# Uma célula muito longa é quase sempre uma tabela de constantes; o começo dela
# basta para a IA reconhecer o que é.
MAX_POR_CELULA = 2500

# Teto do retrato inteiro. Os exemplos do repositório vão de 5 a 24 KB de fonte,
# entao isto cabe todos; o limite existe para o caso de um notebook que cresceu
# demais numa sessao longa.
MAX_TOTAL = 40_000

# Importadas, e não escritas à mão: a primeira versão deste módulo usou chaves
# em inglês ("error", "new") enquanto as constantes são em português, e o mapa
# descartava três dos quatro estados sem reclamar de nada.
from .nb import STATUS_ERROR, STATUS_NEW, STATUS_OK, STATUS_RUNNING

_ROTULOS = {
    STATUS_OK: "executada com sucesso",
    STATUS_ERROR: "FALHOU na última execução",
    STATUS_RUNNING: "executando agora",
    STATUS_NEW: "ainda não executada",
}


def _resumir(fonte: str) -> str:
    if len(fonte) <= MAX_POR_CELULA:
        return fonte
    cortado = fonte[:MAX_POR_CELULA].rsplit("\n", 1)[0]
    restante = len(fonte) - len(cortado)
    return f"{cortado}\n# … (mais {restante} caracteres nesta célula)"


def retrato(notebook, titulo: str = "") -> str:
    """O notebook aberto, em texto, para ir junto do pedido do usuário.

    Devolve string vazia quando não há nada aberto — nesse caso não vale gastar
    prompt dizendo que o notebook está vazio.
    """
    celulas = getattr(notebook, "cells", None) or []
    if not celulas:
        return ""

    linhas = ["(Notebook aberto agora no aplicativo"]
    if titulo:
        linhas[0] += f" — {titulo}"
    linhas[0] += f", {len(celulas)} células.)"
    linhas.append(
        "Use estes números para se referir às células: eles são os mesmos que o "
        "usuário vê na tela."
    )
    linhas.append("")

    total = 0
    truncou = False
    for i, celula in enumerate(celulas, start=1):
        tipo = "código" if celula.kind == "code" else "texto"
        estado = _ROTULOS.get(getattr(celula, "status", ""), "")
        cabeca = f"--- célula {i} ({tipo}{', ' + estado if estado else ''}) ---"
        corpo = _resumir(celula.source or "")
        bloco = f"{cabeca}\n{corpo}"
        if total + len(bloco) > MAX_TOTAL:
            truncou = True
            linhas.append(
                f"--- células {i} a {len(celulas)} omitidas: o notebook ficou "
                "grande demais para caber aqui ---")
            break
        linhas.append(bloco)
        total += len(bloco)

    if truncou:
        linhas.append(
            "Se precisar de uma das células omitidas, peça ao usuário para "
            "colar o conteúdo dela.")
    return "\n".join(linhas)


def montar_pedido(texto: str, notebook=None, notas: list[str] | None = None,
                  titulo: str = "") -> str:
    """Junta o pedido do usuário com o que a IA precisa saber para atendê-lo.

    A ordem importa: primeiro o contexto, depois o pedido. O pedido é a última
    coisa que o modelo lê, e é o que ele tem de atender.
    """
    partes = []
    if notebook is not None:
        foto = retrato(notebook, titulo)
        if foto:
            partes.append(foto)
    if notas:
        partes.append(
            "(Contexto do aplicativo — resultados de execuções recentes:\n"
            + "\n".join(notas) + ")")
    if not partes:
        return texto
    partes.append(f"Pedido do usuário: {texto}")
    return "\n\n".join(partes)
