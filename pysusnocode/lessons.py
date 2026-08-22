"""Memória de aprendizado do PySusNoCode.

Cada vez que o aplicativo encontra um erro ao executar uma célula e consegue
corrigi-lo, extrai uma "lição" (uma linha) e guarda aqui. As lições são
injetadas no prompt de sistema das próximas conversas, de modo que o app
aprende com os próprios erros entre sessões.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import date

from .config import APP_DIR, LESSONS_FILE

MAX_LESSONS_IN_PROMPT = 40
MAX_LESSONS_STORED = 200

# Lições pré-carregadas com armadilhas conhecidas do PySUS em notebooks.
SEED_LESSONS = [
    "Em notebooks (Jupyter/Colab) NUNCA use asyncio.run(): o loop de eventos ja esta rodando. Use 'await' direto na celula (top-level await) ou prefira as funcoes sincronas de alto nivel do pysus (sinan, sim, sinasc, sih, sia, cnes, pni, ibge).",
    "A primeira celula de codigo deve ser '%pip install pysus -q' — funciona tanto neste aplicativo quanto no Google Colab.",
    "Prefira as funcoes de alto nivel do pysus 2.x com as_dataframe=True para receber um pandas.DataFrame pronto (ex.: sinan(disease='DENG', year=2024, as_dataframe=True)).",
    "Downloads do DATASUS podem demorar varios minutos; em testes iniciais baixe apenas 1 ano e, quando o dataset for estadual, apenas 1 UF.",
    "Codigo encontrado na internet com 'from pysus.online_data import ...' ou 'from pysus.ftp.databases ...' e da versao 1.x (antiga). Na 2.x use 'from pysus import sinan, sim, ...' ou o orquestrador pysus.api.client.PySUS.",
    "Colunas de DataFrames do DATASUS geralmente vem como texto (dtype object). Converta com pd.to_numeric(..., errors='coerce') ou pd.to_datetime(..., errors='coerce') antes de agregar ou plotar.",
    "Datas do SINAN como DT_NOTIFIC podem vir no formato YYYYMMDD; use pd.to_datetime(df['DT_NOTIFIC'], format='%Y%m%d', errors='coerce').",
]


class LessonStore:
    def __init__(self) -> None:
        self.lessons: list[dict] = []
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        try:
            if LESSONS_FILE.exists():
                self.lessons = json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
            else:
                self.lessons = [
                    {"licao": t, "origem": "pre-carregada", "data": str(date.today())}
                    for t in SEED_LESSONS
                ]
                self.save()
        except Exception:
            self.lessons = [
                {"licao": t, "origem": "pre-carregada", "data": str(date.today())}
                for t in SEED_LESSONS
            ]

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        LESSONS_FILE.write_text(
            json.dumps(self.lessons[-MAX_LESSONS_STORED:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _norm(text: str) -> str:
        text = unicodedata.normalize("NFKD", text.lower().strip())
        return "".join(c for c in text if not unicodedata.combining(c))

    def add(self, licao: str, origem: str = "erro corrigido") -> bool:
        """Guarda uma nova lição; devolve False se já existia uma equivalente."""
        licao = " ".join(licao.split())
        if not licao or len(licao) < 15:
            return False
        norm = self._norm(licao)
        for existing in self.lessons:
            if self._norm(existing["licao"]) == norm:
                return False
        self.lessons.append(
            {"licao": licao, "origem": origem, "data": str(date.today())}
        )
        self.save()
        return True

    def for_prompt(self) -> str:
        """Bloco de texto com as lições, para injetar no prompt de sistema."""
        recent = self.lessons[-MAX_LESSONS_IN_PROMPT:]
        if not recent:
            return ""
        lines = "\n".join(f"- {item['licao']}" for item in recent)
        return lines

    def count(self) -> int:
        return len(self.lessons)
