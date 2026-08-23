"""Temas do PySusNoCode (acessibilidade: contraste e cores).

Todos os textos exibidos em HTML recebem cor EXPLÍCITA a partir destes tokens —
nunca herdamos a cor do sistema, para que o modo escuro do Windows jamais
produza texto claro sobre fundo claro (ou vice-versa).
"""

from __future__ import annotations

LIGHT = {
    # base da interface
    "window": "#f0f2f5",
    "base": "#ffffff",
    "text": "#1f2933",
    "muted": "#52606d",
    "border": "#cbd5e0",
    "highlight": "#2b6cb0",
    "highlight_text": "#ffffff",
    "button_bg": "#ffffff",
    "button_hover": "#e6ecf3",
    "button_pressed": "#d7e0ea",
    # balões do chat
    "chat_user_bg": "#e6f0fa",
    "chat_user_fg": "#1a365d",
    "chat_assistant_bg": "#f7f7f2",
    "chat_assistant_fg": "#2d3020",
    "chat_app_bg": "#fff8e1",
    "chat_app_fg": "#7b5e00",
    "chat_error_bg": "#fdecea",
    "chat_error_fg": "#9b2c2c",
    "code_bg": "#eef1f4",
    "code_fg": "#1f2933",
    # células do notebook
    "cell_bg": "#ffffff",
    "cell_border_code": "#cbd5e0",
    "cell_border_md": "#ecc94b",
    "cell_title_fg": "#2d3748",
    "editor_bg_code": "#f8fafc",
    "editor_bg_md": "#fffbea",
    "editor_fg": "#1f2933",
    "editor_border": "#e2e8f0",
    "output_bg": "#fdfdfd",
    "output_fg": "#2d3748",
    "output_err_bg": "#fdecea",
    "output_err_fg": "#9b2c2c",
    "stream_err_fg": "#9b2c2c",
    # status das células
    "st_new": "#718096",
    "st_run": "#b7791f",
    "st_ok": "#276749",
    "st_err": "#9b2c2c",
    # painel do notebook
    "nb_scroll_bg": "#edf2f7",
    "nb_empty_fg": "#718096",
}

DARK = {
    "window": "#1b202a",
    "base": "#232a36",
    "text": "#e6e9ef",
    "muted": "#9aa5b1",
    "border": "#3a4354",
    "highlight": "#4c8fd6",
    # Texto escuro sobre o azul claro do destaque: branco daria apenas
    # 3,4:1 de contraste (abaixo do mínimo acessível de 4,5:1).
    "highlight_text": "#0f131a",
    "button_bg": "#2e3644",
    "button_hover": "#3b4557",
    "button_pressed": "#47536a",
    "chat_user_bg": "#1f3a5f",
    "chat_user_fg": "#d5e6fa",
    "chat_assistant_bg": "#2b3040",
    "chat_assistant_fg": "#eceadf",
    "chat_app_bg": "#3b3320",
    "chat_app_fg": "#f0d580",
    "chat_error_bg": "#46262a",
    "chat_error_fg": "#f5b8b8",
    "code_bg": "#171c25",
    "code_fg": "#d8dee9",
    "cell_bg": "#232a36",
    "cell_border_code": "#3a4354",
    "cell_border_md": "#8a7a30",
    "cell_title_fg": "#dfe4ec",
    "editor_bg_code": "#171c25",
    "editor_bg_md": "#2e2a1a",
    "editor_fg": "#d8dee9",
    "editor_border": "#3a4354",
    "output_bg": "#1a1f29",
    "output_fg": "#d8dee9",
    "output_err_bg": "#3a2326",
    "output_err_fg": "#f5b8b8",
    "stream_err_fg": "#f5b8b8",
    "st_new": "#a0aec0",
    "st_run": "#ecc94b",
    "st_ok": "#48bb78",
    "st_err": "#fc8181",
    "nb_scroll_bg": "#151a22",
    "nb_empty_fg": "#9aa5b1",
}

THEME_NAMES = {"claro": "Claro", "escuro": "Escuro"}


def tokens(theme_name: str) -> dict:
    return DARK if theme_name == "escuro" else LIGHT


def app_stylesheet(t: dict) -> str:
    """Folha de estilo global: garante contraste de texto em TODOS os
    controles, inclusive na lista aberta dos seletores (o popup do QComboBox,
    que não segue a paleta da janela) e nas dicas de ajuda."""
    return f"""
    QComboBox {{
        color: {t['text']};
        background: {t['base']};
        border: 1px solid {t['border']};
        border-radius: 4px;
        padding: 3px 6px;
        min-height: 20px;
    }}
    QComboBox:disabled {{ color: {t['muted']}; }}
    QComboBox::drop-down {{ border: 0; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {t['base']};
        color: {t['text']};
        border: 1px solid {t['border']};
        selection-background-color: {t['highlight']};
        selection-color: {t['highlight_text']};
        outline: none;
    }}
    QPushButton {{
        color: {t['text']};
        background: {t['button_bg']};
        border: 1px solid {t['border']};
        border-radius: 4px;
        padding: 5px 10px;
    }}
    QPushButton:hover {{ background: {t['button_hover']}; }}
    QPushButton:pressed {{ background: {t['button_pressed']}; }}
    QPushButton:disabled {{ color: {t['muted']}; border-color: {t['muted']}; }}
    QCheckBox {{ color: {t['text']}; spacing: 6px; }}
    QCheckBox:disabled {{ color: {t['muted']}; }}
    QSpinBox, QLineEdit, QPlainTextEdit {{
        color: {t['text']};
        background: {t['base']};
        border: 1px solid {t['border']};
        border-radius: 4px;
        selection-background-color: {t['highlight']};
        selection-color: {t['highlight_text']};
    }}
    QToolTip {{
        color: {t['text']};
        background: {t['base']};
        border: 1px solid {t['border']};
        padding: 4px;
    }}
    QMenu {{ background: {t['base']}; color: {t['text']}; border: 1px solid {t['border']}; }}
    QMenu::item:selected {{ background: {t['highlight']}; color: {t['highlight_text']}; }}
    QScrollBar:vertical, QScrollBar:horizontal {{ background: {t['window']}; }}
    QDialog, QMessageBox {{ background: {t['window']}; color: {t['text']}; }}
    QDialog QLabel, QMessageBox QLabel {{ color: {t['text']}; }}
    """


def apply_app_palette(app, t: dict) -> None:
    """Aplica uma paleta Qt coerente com o tema em TODA a interface,
    para que nenhum controle herde cores do modo claro/escuro do Windows."""
    from PySide6.QtGui import QColor, QPalette

    p = QPalette()
    window = QColor(t["window"])
    base = QColor(t["base"])
    text = QColor(t["text"])
    muted = QColor(t["muted"])

    p.setColor(QPalette.Window, window)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, window)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.PlaceholderText, muted)
    p.setColor(QPalette.Button, window)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.ToolTipBase, base)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Highlight, QColor(t["highlight"]))
    p.setColor(QPalette.HighlightedText, QColor(t["highlight_text"]))
    p.setColor(QPalette.Link, QColor(t["highlight"]))
    p.setColor(QPalette.Disabled, QPalette.Text, muted)
    p.setColor(QPalette.Disabled, QPalette.ButtonText, muted)
    p.setColor(QPalette.Disabled, QPalette.WindowText, muted)
    app.setPalette(p)
