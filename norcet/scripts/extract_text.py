#!/usr/bin/env python3
from __future__ import annotations

import logging
from pathlib import Path

import fitz
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw_pdfs"
OUT_DIR = ROOT / "extracted_text"


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = [(page.extract_text() or "") for page in pdf.pages]
        text = "\n\n".join(pages).strip()
        if text:
            return text
    except Exception:  # noqa: BLE001
        pass

    doc = fitz.open(pdf_path)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n\n".join(pages).strip()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for pdf_file in sorted(RAW_DIR.glob("*/*.pdf")):
        year = pdf_file.parent.name
        out_path = OUT_DIR / f"{year}_{pdf_file.stem}.txt"
        text = extract_pdf_text(pdf_file)
        out_path.write_text(f"__SOURCE_PDF__:{pdf_file.name}\n\n{text}\n", encoding="utf-8")
        logging.info("Extracted %s", out_path)


if __name__ == "__main__":
    main()
