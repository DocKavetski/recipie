import os
from pathlib import Path


def open_pdf(pdf_path: str | Path) -> str:
    path = Path(pdf_path).resolve()
    os.startfile(path)  # type: ignore[attr-defined]
    return str(path)
