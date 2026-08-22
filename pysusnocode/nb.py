"""Modelo do notebook em memória e exportação para .ipynb (Google Colab)."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

_ids = itertools.count(1)

STATUS_NEW = "nova"
STATUS_RUNNING = "executando"
STATUS_OK = "ok"
STATUS_ERROR = "erro"


@dataclass
class Cell:
    kind: str                       # "code" | "markdown"
    source: str
    cell_id: int = field(default_factory=lambda: next(_ids))
    status: str = STATUS_NEW
    outputs: list[dict] = field(default_factory=list)
    execution_count: int | None = None
    fix_attempts: int = 0


class Notebook:
    def __init__(self) -> None:
        self.cells: list[Cell] = []

    def add(self, kind: str, source: str) -> Cell:
        cell = Cell(kind=kind, source=source)
        self.cells.append(cell)
        return cell

    def remove(self, cell: Cell) -> None:
        if cell in self.cells:
            self.cells.remove(cell)

    def index_of(self, cell: Cell) -> int:
        return self.cells.index(cell)

    def clear(self) -> None:
        self.cells.clear()

    # ------------------------------------------------------------------
    def to_ipynb(self) -> dict:
        import nbformat
        from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

        nb_cells = []
        for cell in self.cells:
            if cell.kind == "markdown":
                nb_cells.append(new_markdown_cell(cell.source))
            else:
                code_cell = new_code_cell(cell.source)
                code_cell["execution_count"] = cell.execution_count
                outputs = []
                for out in cell.outputs:
                    try:
                        outputs.append(nbformat.from_dict(out))
                    except Exception:  # noqa: BLE001
                        pass
                code_cell["outputs"] = outputs
                nb_cells.append(code_cell)

        notebook = new_notebook(
            cells=nb_cells,
            metadata={
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {"name": "python"},
                "colab": {"provenance": []},
            },
        )
        return notebook

    def save_ipynb(self, path: str | Path) -> None:
        import nbformat

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            nbformat.write(self.to_ipynb(), handle)

    # ------------------------------------------------------------------
    def as_clipboard_text(self) -> str:
        """Todas as células num único texto, pronto para colar no Colab
        (formato de células `# %%` reconhecido por VS Code/Jupytext)."""
        chunks = []
        for i, cell in enumerate(self.cells, start=1):
            if cell.kind == "markdown":
                commented = "\n".join(f"# {line}" for line in cell.source.splitlines())
                chunks.append(f"# %% [markdown] — Célula {i}\n{commented}")
            else:
                chunks.append(f"# %% Célula {i}\n{cell.source}")
        return "\n\n".join(chunks)
