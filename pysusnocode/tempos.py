"""Quanto costuma demorar, medido neste computador.

O aplicativo tem duas esperas, e elas não se parecem em nada:

- **a IA pensando** — depende do modelo, do tamanho do prompt e da internet;
- **a célula executando** — depende do arquivo que o DATASUS vai mandar.

Quem não programa não distingue as duas: vê a tela parada e conclui que travou.
Este módulo mede cada uma separadamente e guarda o histórico, para que a
interface possa dizer "isso costuma levar mais ou menos tanto" em vez de deixar
a pessoa no escuro.

Tudo fica **neste computador**, num arquivo dentro da pasta do aplicativo. Nada
é enviado para lugar nenhum: é o próprio uso da pessoa que vira a estimativa.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .config import APP_DIR

ARQUIVO = APP_DIR / "tempos.json"

# Quantas medições guardar por tipo. O bastante para uma mediana estável e
# pouco o suficiente para o arquivo continuar minúsculo.
MAXIMO = 120

# Abaixo disto não arriscamos uma estimativa: três medidas não fazem média.
MINIMO_PARA_ESTIMAR = 3

IA = "ia"                    # do envio até a resposta terminar
IA_PRIMEIRA = "ia_primeira"  # do envio até a primeira palavra aparecer
CELULA = "celula"            # execução de uma célula no kernel

_trava = threading.Lock()
_memoria: dict[str, list[float]] | None = None


def _carregar() -> dict[str, list[float]]:
    global _memoria
    if _memoria is not None:
        return _memoria
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        _memoria = {
            chave: [float(v) for v in valores][-MAXIMO:]
            for chave, valores in dados.items()
            if isinstance(valores, list)
        }
    except Exception:  # noqa: BLE001
        _memoria = {}
    return _memoria


def _gravar() -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        ARQUIVO.write_text(json.dumps(_memoria, ensure_ascii=False),
                           encoding="utf-8")
    except Exception as erro:  # noqa: BLE001
        from .diag import registrar as anotar

        anotar("nao consegui gravar os tempos", f"{type(erro).__name__}: {erro}")


def _chave(tipo: str, contexto: str = "") -> str:
    return f"{tipo}|{contexto}" if contexto else tipo


def registrar(tipo: str, segundos: float, contexto: str = "") -> None:
    """Guarda uma medição. Nunca levanta: medir não pode quebrar o aplicativo.

    ``contexto`` separa medições que não se misturam — o modelo da IA, por
    exemplo. Um Opus e um GPT-nano têm tempos diferentes, e uma média dos dois
    não descreve nenhum dos dois.
    """
    # Zero e legitimo: ha celula que executa num piscar. Negativo nao
    # existe, e mais de uma hora e relogio do sistema tendo mudado.
    if segundos < 0 or segundos > 3600:
        return
    try:
        with _trava:
            dados = _carregar()
            for chave in {_chave(tipo), _chave(tipo, contexto)}:
                lista = dados.setdefault(chave, [])
                lista.append(round(float(segundos), 2))
                del lista[:-MAXIMO]
            _gravar()
    except Exception:  # noqa: BLE001
        pass


def amostras(tipo: str, contexto: str = "") -> list[float]:
    """As medições de um tipo, preferindo as do contexto quando houver o bastante."""
    with _trava:
        dados = _carregar()
        especificas = dados.get(_chave(tipo, contexto), []) if contexto else []
        if len(especificas) >= MINIMO_PARA_ESTIMAR:
            return list(especificas)
        return list(dados.get(_chave(tipo), []))


def _percentil(valores: list[float], fracao: float) -> float:
    ordenados = sorted(valores)
    posicao = max(0, min(len(ordenados) - 1, round(fracao * (len(ordenados) - 1))))
    return ordenados[posicao]


def mediana(tipo: str, contexto: str = "") -> float | None:
    valores = amostras(tipo, contexto)
    if len(valores) < MINIMO_PARA_ESTIMAR:
        return None
    return _percentil(valores, 0.5)


def em_palavras(segundos: float) -> str:
    """Duração em português, arredondada como gente fala."""
    if segundos < 10:
        return f"{segundos:.0f} segundos"
    if segundos < 60:
        return f"{round(segundos / 5) * 5:.0f} segundos"
    minutos = segundos / 60
    if minutos < 2:
        return "cerca de 1 minuto"
    if minutos < 10:
        return f"cerca de {minutos:.0f} minutos"
    return f"mais de {int(minutos // 5) * 5} minutos"


def estimativa(tipo: str, contexto: str = "") -> str:
    """Frase curta para a barra de espera, ou vazio quando ainda não dá para dizer.

    Usa a mediana, e acrescenta o caso demorado (percentil 80) só quando ele é
    bem maior — avisar que "às vezes leva o dobro" evita que a pessoa desista
    justamente na vez lenta.
    """
    valores = amostras(tipo, contexto)
    if len(valores) < MINIMO_PARA_ESTIMAR:
        return ""
    tipico = _percentil(valores, 0.5)
    # "costuma levar 0 segundos" nao informa nada e ainda parece defeito. Abaixo
    # de dois segundos a espera nem chega a ser percebida: melhor calar.
    if tipico < 2:
        return ""
    demorado = _percentil(valores, 0.8)
    frase = f"costuma levar {em_palavras(tipico)}"
    if demorado > tipico * 1.6:
        frase += f", às vezes {em_palavras(demorado)}"
    return frase


def resumo() -> list[dict]:
    """O que foi medido até agora, para mostrar nas Configurações."""
    rotulos = {
        IA: "Resposta da IA, do envio ao fim",
        IA_PRIMEIRA: "Até a IA começar a escrever",
        CELULA: "Execução de uma célula",
    }
    linhas = []
    with _trava:
        dados = _carregar()
    for tipo, rotulo in rotulos.items():
        valores = dados.get(tipo, [])
        if not valores:
            linhas.append({"o_que": rotulo, "medicoes": 0, "tipico": "—",
                           "demorado": "—"})
            continue
        linhas.append({
            "o_que": rotulo,
            "medicoes": len(valores),
            "tipico": em_palavras(_percentil(valores, 0.5)),
            "demorado": em_palavras(_percentil(valores, 0.9)),
        })
    return linhas


def esquecer() -> None:
    """Apaga o histórico. Útil depois de trocar de máquina ou de conexão."""
    global _memoria
    with _trava:
        _memoria = {}
        _gravar()


class Cronometro:
    """Mede um trecho e registra sozinho ao sair do ``with``.

    Marca também o instante da primeira resposta, quando há streaming::

        with Cronometro(tempos.IA, modelo) as c:
            ...
            c.primeira_resposta()   # na primeira palavra que chega
    """

    def __init__(self, tipo: str, contexto: str = ""):
        self.tipo = tipo
        self.contexto = contexto
        self.inicio = 0.0
        self._marcou_primeira = False

    def __enter__(self) -> "Cronometro":
        self.inicio = time.monotonic()
        return self

    def primeira_resposta(self) -> None:
        if self._marcou_primeira or self.tipo != IA:
            return
        self._marcou_primeira = True
        registrar(IA_PRIMEIRA, time.monotonic() - self.inicio, self.contexto)

    def __exit__(self, tipo_erro, erro, tb) -> None:
        if erro is None:
            registrar(self.tipo, time.monotonic() - self.inicio, self.contexto)
