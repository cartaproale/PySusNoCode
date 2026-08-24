"""Modal de visualização ampliada da saída de uma célula.

Além de mostrar a saída inteira, permite aproximar e afastar (zoom) com
botões, atalhos (Ctrl+ + / Ctrl+ − / Ctrl+0) e Ctrl+roda do mouse, e ainda
copiar ou salvar o gráfico — útil para montar relatórios e boletins.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

ESCALAS = [0.25, 0.35, 0.5, 0.67, 0.8, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0]
ESCALA_PADRAO = 1.0


class OutputDialog(QDialog):
    def __init__(self, title: str, outputs: list[dict], tokens: dict, font_px: int, parent=None):
        super().__init__(parent)
        from .cell_widget import imagens_das_saidas

        self.outputs = outputs
        self.tokens = tokens
        self.font_px = font_px
        self.escala = ESCALA_PADRAO
        self.imagens = imagens_das_saidas(outputs)

        self.setWindowTitle(title)
        self.setSizeGripEnabled(True)
        tela = self.screen() or QApplication.primaryScreen()
        if tela is not None:
            area = tela.availableGeometry()
            self.resize(int(area.width() * 0.85), int(area.height() * 0.85))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- barra de ferramentas ---------------------------------------
        barra = QHBoxLayout()

        self.menos_btn = QPushButton("🔍−")
        self.menos_btn.setToolTip("Afastar (Ctrl+−)")
        self.menos_btn.clicked.connect(lambda: self.ajustar_zoom(-1))
        barra.addWidget(self.menos_btn)

        self.zoom_label = QLabel()
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setMinimumWidth(56)
        barra.addWidget(self.zoom_label)

        self.mais_btn = QPushButton("🔍+")
        self.mais_btn.setToolTip("Aproximar (Ctrl++)")
        self.mais_btn.clicked.connect(lambda: self.ajustar_zoom(+1))
        barra.addWidget(self.mais_btn)

        self.original_btn = QPushButton("100%")
        self.original_btn.setToolTip("Voltar ao tamanho original (Ctrl+0)")
        self.original_btn.clicked.connect(self.zoom_original)
        barra.addWidget(self.original_btn)

        self.caber_btn = QPushButton("↔ Caber na janela")
        self.caber_btn.setToolTip("Ajustar o zoom para o gráfico caber na largura da janela")
        self.caber_btn.clicked.connect(self.ajustar_para_caber)
        barra.addWidget(self.caber_btn)

        barra.addStretch(1)

        self.copiar_btn = QPushButton("📋 Copiar imagem")
        self.copiar_btn.setToolTip(
            "Copiar o gráfico para a área de transferência (Ctrl+C) — cole no Word, "
            "PowerPoint, e-mail…"
        )
        self.copiar_btn.clicked.connect(self.copiar_imagem)
        barra.addWidget(self.copiar_btn)

        self.salvar_btn = QPushButton("💾 Salvar imagem…")
        self.salvar_btn.setToolTip("Salvar o gráfico como arquivo PNG")
        self.salvar_btn.clicked.connect(self.salvar_imagem)
        barra.addWidget(self.salvar_btn)

        self.copiar_texto_btn = QPushButton("📄 Copiar texto")
        self.copiar_texto_btn.setToolTip("Copiar o texto da saída (tabelas, números, mensagens)")
        self.copiar_texto_btn.clicked.connect(self.copiar_texto)
        barra.addWidget(self.copiar_texto_btn)

        fechar_btn = QPushButton("Fechar (Esc)")
        fechar_btn.setDefault(True)
        fechar_btn.clicked.connect(self.accept)
        barra.addWidget(fechar_btn)

        layout.addLayout(barra)

        # --- conteúdo ----------------------------------------------------
        self.browser = QTextBrowser()
        self.browser.setStyleSheet(
            f"QTextBrowser{{background:{tokens['output_bg']};color:{tokens['output_fg']};"
            f"border:1px solid {tokens['border']};border-radius:4px;}}"
        )
        self.browser.viewport().installEventFilter(self)   # Ctrl + roda do mouse
        layout.addWidget(self.browser, stretch=1)

        self.dica = QLabel(
            "Dica: Ctrl+roda do mouse ou Ctrl+ + / Ctrl+ − para aproximar e afastar."
        )
        self.dica.setStyleSheet(f"color:{tokens['muted']};font-size:{max(10, font_px - 2)}px;")
        layout.addWidget(self.dica)

        tem_imagem = bool(self.imagens)
        self.copiar_btn.setEnabled(tem_imagem)
        self.salvar_btn.setEnabled(tem_imagem)
        self.caber_btn.setEnabled(tem_imagem)

        # --- atalhos ------------------------------------------------------
        for sequencia in (QKeySequence.ZoomIn, QKeySequence("Ctrl+="), QKeySequence("Ctrl++")):
            QShortcut(sequencia, self, activated=lambda: self.ajustar_zoom(+1))
        for sequencia in (QKeySequence.ZoomOut, QKeySequence("Ctrl+-")):
            QShortcut(sequencia, self, activated=lambda: self.ajustar_zoom(-1))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.zoom_original)
        QShortcut(QKeySequence.Copy, self, activated=self.copiar_imagem)
        QShortcut(QKeySequence.Save, self, activated=self.salvar_imagem)

        self._render()

    # ------------------------------------------------------------------
    def _render(self) -> None:
        from .cell_widget import build_outputs_html

        posicao = self.browser.verticalScrollBar().value()
        html = build_outputs_html(
            self.outputs, self.browser.document(), self.tokens, self.font_px + 1, self.escala
        )
        self.browser.setHtml(html)
        self.browser.verticalScrollBar().setValue(posicao)
        self.zoom_label.setText(f"{round(self.escala * 100)}%")
        self.menos_btn.setEnabled(self.escala > ESCALAS[0])
        self.mais_btn.setEnabled(self.escala < ESCALAS[-1])

    def ajustar_zoom(self, passos: int) -> None:
        atual = min(range(len(ESCALAS)), key=lambda i: abs(ESCALAS[i] - self.escala))
        novo = max(0, min(len(ESCALAS) - 1, atual + passos))
        if ESCALAS[novo] != self.escala:
            self.escala = ESCALAS[novo]
            self._render()

    def zoom_original(self) -> None:
        self.escala = ESCALA_PADRAO
        self._render()

    def ajustar_para_caber(self) -> None:
        """Escolhe o zoom que faz o maior gráfico caber na largura visível."""
        if not self.imagens:
            return
        largura_disponivel = max(200, self.browser.viewport().width() - 30)
        largura_maxima = max(img.width() for img in self.imagens)
        alvo = largura_disponivel / largura_maxima
        # maior escala da lista que ainda cabe (ou a menor, se nada couber)
        cabem = [e for e in ESCALAS if e <= alvo]
        self.escala = cabem[-1] if cabem else ESCALAS[0]
        self._render()

    # ------------------------------------------------------------------
    def copiar_imagem(self) -> None:
        """Copia o gráfico (ou toda a saída renderizada) para a área de
        transferência, em tamanho original — pronto para colar em relatórios."""
        imagem = self.imagens[0] if len(self.imagens) == 1 else self._renderizar_tudo()
        if imagem is None or imagem.isNull():
            QMessageBox.information(
                self, "Nada para copiar", "Esta saída não tem imagem para copiar."
            )
            return
        QGuiApplication.clipboard().setImage(imagem)
        quantas = "o gráfico" if len(self.imagens) == 1 else "a saída inteira"
        self.dica.setText(
            f"✅ Copiado: {quantas} está na área de transferência — use Ctrl+V para colar."
        )

    def salvar_imagem(self) -> None:
        imagem = self.imagens[0] if len(self.imagens) == 1 else self._renderizar_tudo()
        if imagem is None or imagem.isNull():
            QMessageBox.information(
                self, "Nada para salvar", "Esta saída não tem imagem para salvar."
            )
            return
        sugestao = str(Path.home() / "Documents" / "PySusNoCode" / "grafico.png")
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar imagem", sugestao, "Imagem PNG (*.png)"
        )
        if not caminho:
            return
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        if imagem.save(caminho, "PNG"):
            self.dica.setText(f"✅ Imagem salva em {caminho}")
        else:
            QMessageBox.critical(self, "Erro", "Não consegui salvar a imagem.")

    def copiar_texto(self) -> None:
        QGuiApplication.clipboard().setText(self.browser.toPlainText())
        self.dica.setText("✅ Texto da saída copiado para a área de transferência.")

    def _renderizar_tudo(self) -> QImage | None:
        """Desenha todo o conteúdo (texto + gráficos) numa única imagem,
        inclusive as partes fora da área visível."""
        documento = self.browser.document()
        largura_anterior = documento.textWidth()
        # A largura precisa comportar o maior gráfico, senão ele sairia
        # espremido na imagem final.
        largura_graficos = max((img.width() for img in self.imagens), default=0)
        largura = max(400, int(documento.idealWidth()) + 20, largura_graficos + 40)
        documento.setTextWidth(largura)
        altura = max(100, int(documento.size().height()) + 20)
        imagem = QImage(largura, altura, QImage.Format_ARGB32)
        imagem.fill(self.tokens["output_bg"])
        pintor = QPainter(imagem)
        pintor.translate(10, 10)
        documento.drawContents(pintor)
        pintor.end()
        documento.setTextWidth(largura_anterior)   # não bagunça a exibição
        return imagem

    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):  # noqa: N802
        if (
            obj is self.browser.viewport()
            and event.type() == QEvent.Wheel
            and event.modifiers() & Qt.ControlModifier
        ):
            self.ajustar_zoom(+1 if event.angleDelta().y() > 0 else -1)
            return True
        return super().eventFilter(obj, event)
