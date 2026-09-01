"""Janela “Versões e fontes”: o que o aplicativo usa e o que existe lá fora.

Responde a uma pergunta de manutenção, não de uso: *mudou alguma coisa desde a
última vez que auditei?* Por isso o destaque é a coluna da direita e o aviso do
rodapé — o resto é contexto.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .. import __version__

CORES = {
    "desatualizada": "#b7791f",
    "ausente": "#c53030",
    "em dia": "#2f855a",
    "?": "#718096",
}
SIMBOLOS = {
    "desatualizada": "⬆ há versão nova",
    "ausente": "✖ não encontrada",
    "em dia": "✓ em dia",
    "?": "— não verificado",
}


class _Levantamento(QThread):
    """Consulta em segundo plano: a rede não pode travar a janela."""

    pronto = Signal(object)
    falhou = Signal(str)

    def run(self) -> None:
        try:
            from ..versoes import levantar

            self.pronto.emit(levantar(consultar_rede=True))
        except Exception as exc:  # noqa: BLE001
            self.falhou.emit(f"{type(exc).__name__}: {exc}")


class VersoesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Versões e fontes — PySusNoCode")
        self.setMinimumSize(760, 560)
        self.worker: _Levantamento | None = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            f"<b>PySusNoCode {__version__}</b><br>"
            "As bibliotecas e os sistemas de onde vêm os dados. A coluna "
            "<i>Existe hoje</i> mostra o que há de mais recente — quando ela "
            "diverge, vale auditar antes de publicar."
        ))

        layout.addWidget(QLabel("<b>Bibliotecas</b>"))
        self.tabela_libs = self._nova_tabela(
            ["Biblioteca", "Em uso", "Existe hoje", "Situação", "Para que serve"]
        )
        layout.addWidget(self.tabela_libs)

        layout.addWidget(QLabel("<b>Fontes de dados</b>"))
        self.tabela_fontes = self._nova_tabela(
            ["Sistema", "Resposta", "Dado até", "Situação", "Para que serve"]
        )
        layout.addWidget(self.tabela_fontes)

        # Como (e quando) os exemplos foram validados — a resposta à pergunta
        # "posso confiar nesses notebooks?", escrita onde o usuário procura
        # por procedência. Os números vêm do exemplos.json, que carrega o
        # resumo do VALIDACAO.md gerado a cada validação completa.
        layout.addWidget(QLabel("<b>Como os exemplos são validados</b>"))
        self.validacao_label = QLabel()
        self.validacao_label.setWordWrap(True)
        self.validacao_label.setOpenExternalLinks(True)
        self.validacao_label.setText(self._texto_validacao())
        layout.addWidget(self.validacao_label)

        self.resumo = QLabel("Consultando…")
        self.resumo.setWordWrap(True)
        layout.addWidget(self.resumo)

        rodape = QHBoxLayout()
        self.atualizar_btn = QPushButton("🔄 Verificar de novo")
        self.atualizar_btn.clicked.connect(self.consultar)
        rodape.addWidget(self.atualizar_btn)
        self.copiar_btn = QPushButton("📋 Copiar como texto")
        self.copiar_btn.clicked.connect(self._copiar)
        rodape.addWidget(self.copiar_btn)
        rodape.addStretch(1)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        rodape.addWidget(fechar)
        layout.addLayout(rodape)

        self.quadro = None
        self.consultar()

    # ------------------------------------------------------------------
    @staticmethod
    def _texto_validacao() -> str:
        from .. import exemplos as cat

        val = dict(cat.RESUMO_VALIDACAO)
        if not val:
            # o catálogo ainda não foi carregado nesta sessão: lê a cópia local
            try:
                cat.carregar_catalogo(preferir_github=False)
                val = dict(cat.RESUMO_VALIDACAO)
            except Exception:  # noqa: BLE001
                val = {}
        cabeca = ""
        if val.get("data"):
            cabeca = (
                f"Última validação completa: <b>{val['data']}</b> — "
                f"<b>{val.get('funcionando', '?')} de {val.get('total', '?')}</b> "
                f"notebooks funcionando, contra a PySUS "
                f"{val.get('versao_pysus', '?')}.<br>"
            )
        relatorio = f"{cat.PAGINA}/blob/{cat.RAMO}/VALIDACAO.md"
        return (
            cabeca
            + "Cada exemplo passa por: <b>execução real</b> de todas as células, "
            "baixando dados do DATASUS; <b>verificação de sanidade</b> no fim do "
            "notebook (faixas plausíveis, somas que fecham); <b>sentinelas</b> — "
            "valores-chave comparados entre validações, para pegar deriva; "
            "<b>recontagem independente</b> dos indicadores por uma segunda "
            "fórmula; e <b>valores-ouro</b> conferidos contra TABNET e IBGE/SIDRA. "
            f"<a href='{relatorio}'>Relatório completo, notebook a notebook</a>."
        )

    @staticmethod
    def _nova_tabela(colunas: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(colunas))
        t.setHorizontalHeaderLabels(colunas)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def consultar(self) -> None:
        self.atualizar_btn.setEnabled(False)
        self.resumo.setText("Consultando o PyPI e as fontes de dados…")
        self.worker = _Levantamento(self)
        self.worker.pronto.connect(self._mostrar)
        self.worker.falhou.connect(self._erro)
        self.worker.start()

    def _erro(self, texto: str) -> None:
        self.atualizar_btn.setEnabled(True)
        self.resumo.setText(f"Não consegui levantar as versões: {texto}")

    def _mostrar(self, quadro) -> None:
        self.quadro = quadro
        self.atualizar_btn.setEnabled(True)

        self._preencher(self.tabela_libs, [
            (i.nome, i.em_uso or "—", i.disponivel or "—", i.situacao, i.descricao)
            for i in quadro.bibliotecas
        ])
        self._preencher(self.tabela_fontes, [
            (i.nome, i.em_uso or "—", i.disponivel or "—", i.situacao, i.descricao)
            for i in quadro.fontes
        ])

        atrasadas = quadro.desatualizadas
        fora = [i for i in quadro.fontes if i.situacao == "ausente"]
        partes = []
        if atrasadas:
            nomes = ", ".join(f"<b>{i.nome}</b> ({i.em_uso} → {i.disponivel})"
                              for i in atrasadas)
            partes.append(
                f"⬆ {nomes} têm versão mais nova. Vale auditar o que mudou "
                "antes de publicar: é assim que os aprendizados do kernel "
                "envelhecem."
                if len(atrasadas) > 1 else
                f"⬆ {nomes} tem versão mais nova. Vale auditar o que mudou "
                "antes de publicar: é assim que os aprendizados do kernel "
                "envelhecem."
            )
        if fora:
            partes.append(
                "✖ Não alcancei: " + ", ".join(i.nome for i in fora)
                + ". Pode ser rede bloqueada, VPN ligada ou o serviço fora do ar."
            )
        if not partes:
            partes.append("✓ Tudo em dia: nada mudou desde a última publicação.")
        self.resumo.setText("<br><br>".join(partes))

    def _preencher(self, tabela: QTableWidget, linhas) -> None:
        tabela.setRowCount(len(linhas))
        for r, (nome, uso, disp, situacao, desc) in enumerate(linhas):
            valores = [nome, uso, disp, SIMBOLOS.get(situacao, situacao), desc]
            for c, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if c == 3:
                    from PySide6.QtGui import QColor

                    item.setForeground(QColor(CORES.get(situacao, "#718096")))
                if c in (1, 2):
                    item.setTextAlignment(Qt.AlignCenter)
                tabela.setItem(r, c, item)

    def _copiar(self) -> None:
        from PySide6.QtWidgets import QApplication

        if not self.quadro:
            return
        linhas = [f"PySusNoCode {__version__}", "", "Bibliotecas:"]
        for i in self.quadro.bibliotecas:
            linhas.append(f"  {i.nome}: em uso {i.em_uso or '—'} | "
                          f"existe hoje {i.disponivel or '—'} | {i.situacao}")
        linhas += ["", "Fontes de dados:"]
        for i in self.quadro.fontes:
            extra = f" | {i.disponivel}" if i.disponivel else ""
            linhas.append(f"  {i.nome}: {i.em_uso or '—'}{extra} | {i.situacao}")
        QApplication.clipboard().setText("\n".join(linhas))
        self.copiar_btn.setText("📋 Copiado")
