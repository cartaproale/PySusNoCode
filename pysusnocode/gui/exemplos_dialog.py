"""Janela dos exemplos prontos: escolher, ler do que se trata e abrir.

Muita gente abre o aplicativo sem saber o que pedir. Esta janela responde a
isso mostrando análises que já existem, foram executadas com dados reais e
podem ser abertas com um clique — servindo tanto de resposta pronta quanto de
ponto de partida para adaptar.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from .. import exemplos as cat


class ExemplosDialog(QDialog):
    """Lista os exemplos e devolve, em `escolhido`, o que o usuário abriu."""

    def __init__(self, font_px: int = 13, parent=None):
        super().__init__(parent)
        self.escolhido: dict | None = None
        self.origem = ""
        self.font_px = font_px

        self.setWindowTitle("Exemplos prontos — PySusNoCode")
        self.setSizeGripEnabled(True)
        tela = self.screen() or QApplication.primaryScreen()
        if tela is not None:
            area = tela.availableGeometry()
            self.resize(int(area.width() * 0.68), int(area.height() * 0.72))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.cabecalho = QLabel()
        self.cabecalho.setWordWrap(True)
        layout.addWidget(self.cabecalho)

        divisor = QSplitter(Qt.Horizontal)

        self.arvore = QTreeWidget()
        self.arvore.setHeaderHidden(True)
        self.arvore.setMinimumWidth(320)
        self.arvore.currentItemChanged.connect(self._mostrar_detalhe)
        self.arvore.itemDoubleClicked.connect(self._abrir_se_exemplo)
        divisor.addWidget(self.arvore)

        self.detalhe = QTextBrowser()
        self.detalhe.setOpenExternalLinks(True)
        divisor.addWidget(self.detalhe)
        divisor.setStretchFactor(0, 4)
        divisor.setStretchFactor(1, 6)
        layout.addWidget(divisor, 1)

        rodape = QHBoxLayout()
        self.botao_github = QPushButton("🌐 Ver no GitHub")
        self.botao_github.setToolTip(
            "Abrir o repositório dos exemplos no navegador"
        )
        self.botao_github.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(cat.PAGINA))
        )
        rodape.addWidget(self.botao_github)
        rodape.addStretch(1)

        self.botoes = QDialogButtonBox()
        self.botao_abrir = self.botoes.addButton(
            "📓 Abrir este exemplo", QDialogButtonBox.AcceptRole
        )
        self.botao_abrir.setEnabled(False)
        fechar = self.botoes.addButton("Fechar", QDialogButtonBox.RejectRole)
        self.botoes.accepted.connect(self._abrir)
        self.botoes.rejected.connect(self.reject)
        fechar.setDefault(False)
        rodape.addWidget(self.botoes)
        layout.addLayout(rodape)

        self._carregar()

    # ------------------------------------------------------------------
    def _carregar(self) -> None:
        # A consulta ao GitHub bloqueia até alguns segundos; numa rede
        # controlada ela vai até o fim do tempo antes de cair para a cópia
        # local. O cursor de espera evita a impressão de travamento.
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            exemplos, origem, aviso = cat.carregar_catalogo()
        finally:
            QApplication.restoreOverrideCursor()
        self.origem = origem

        if origem == cat.ORIGEM_GITHUB:
            fonte = "buscados agora no GitHub, na versão mais recente"
        else:
            fonte = "a cópia que veio no instalador"
        texto = (
            f"<b>{len(exemplos)} análises prontas</b>, {fonte}. "
            "Cada uma foi executada do início ao fim com dados reais do DATASUS "
            "antes de ser publicada.<br>"
            "Ao abrir, o notebook entra no aplicativo e você pode executá-lo, "
            "mudar o estado e o ano, ou pedir alterações no chat."
        )
        if aviso:
            texto += f"<br><span style='color:#b5495b;'>⚠ {aviso}</span>"
        self.cabecalho.setText(texto)

        negrito = QFont()
        negrito.setBold(True)
        for grupo, itens in cat.agrupar(exemplos):
            pai = QTreeWidgetItem(self.arvore, [f"{grupo}  ({len(itens)})"])
            pai.setFont(0, negrito)
            pai.setFlags(pai.flags() & ~Qt.ItemIsSelectable)
            for item in itens:
                filho = QTreeWidgetItem(pai, [item.get("titulo", item["arquivo"])])
                filho.setData(0, Qt.UserRole, item)
                filho.setToolTip(0, item.get("descricao", ""))
            pai.setExpanded(True)

    def _item_atual(self) -> dict | None:
        item = self.arvore.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def _mostrar_detalhe(self, atual, _anterior) -> None:
        dados = atual.data(0, Qt.UserRole) if atual else None
        self.botao_abrir.setEnabled(dados is not None)
        if not dados:
            self.detalhe.clear()
            return

        ficha = []
        if dados.get("base"):
            ficha.append(f"Base: <b>{dados['base']}</b>")
        if dados.get("celulas"):
            ficha.append(f"{dados['celulas']} células")
        if dados.get("graficos"):
            ficha.append(f"{dados['graficos']} gráficos")
        if dados.get("tempo"):
            ficha.append(f"Tempo estimado: {dados['tempo']}")

        endereco = f"{cat.PAGINA}/blob/{cat.RAMO}/{dados['arquivo']}"
        self.detalhe.setHtml(
            f"<div style='font-size:{self.font_px + 3}px;'>"
            f"<h2 style='margin-bottom:6px;'>{dados.get('titulo','')}</h2>"
            f"<p style='font-size:{self.font_px + 1}px;'>{dados.get('descricao','')}</p>"
            f"<p style='color:#6b7280;font-size:{self.font_px}px;'>"
            + " · ".join(ficha)
            + "</p>"
            f"<p style='font-size:{self.font_px}px;'>Arquivo: <code>{dados['arquivo']}</code><br>"
            f"<a href='{endereco}'>Ver este notebook no GitHub</a></p></div>"
        )

    def _abrir_se_exemplo(self, item, _coluna) -> None:
        if item and item.data(0, Qt.UserRole):
            self._abrir()

    def _abrir(self) -> None:
        dados = self._item_atual()
        if dados:
            self.escolhido = dados
            self.accept()
