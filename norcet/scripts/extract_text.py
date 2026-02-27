#!/usr/bin/env python3
from __future__ import annotations

import logging
import re
from pathlib import Path

import fitz
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw_pdfs"
OUT_DIR = ROOT / "extracted_text"

HEADER_PATTERNS = [
    re.compile(r"adda247", re.IGNORECASE),
    re.compile(r"testbook", re.IGNORECASE),
    re.compile(r"career\s*power", re.IGNORECASE),
    re.compile(r"prepp", re.IGNORECASE),
    re.compile(r"scribd", re.IGNORECASE),
]


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned: list[str] = []
    for ln in lines:
        if not ln:
            cleaned.append("")
            continue
        if re.fullmatch(r"\d{1,4}", ln):
            continue
        if any(p.search(ln) for p in HEADER_PATTERNS):
            continue
        ln = re.sub(r"\s+", " ", ln).strip()
        cleaned.append(ln)

    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def extract_with_pdfplumber(pdf_path: Path) -> str:
    chunks: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=True, x_tolerance=2, y_tolerance=2)
            if words:
                words = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
                current_top = None
                line_parts: list[str] = []
                lines: list[str] = []
                for w in words:
                    top = round(w["top"], 1)
                    if current_top is None or abs(top - current_top) <= 2:
                        line_parts.append(w["text"])
                        current_top = top if current_top is None else current_top
                    else:
                        lines.append(" ".join(line_parts))
                        line_parts = [w["text"]]
                        current_top = top
                if line_parts:
                    lines.append(" ".join(line_parts))
                chunks.append("\n".join(lines))
            else:
                chunks.append(page.extract_text() or "")
    return "\n\n".join(chunks)


def extract_with_fitz(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    chunks = []
    for page in doc:
        chunks.append(page.get_text("text"))
    doc.close()
    return "\n\n".join(chunks)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(RAW_DIR.glob("*/*.pdf"))
    for pdf_file in pdf_files:
        year = pdf_file.parent.name
        out_file = OUT_DIR / f"{year}_{pdf_file.stem}.txt"
        try:
            text = extract_with_pdfplumber(pdf_file)
        except Exception:  # noqa: BLE001
            logging.warning("pdfplumber failed, falling back to fitz for %s", pdf_file)
            text = extract_with_fitz(pdf_file)

        cleaned = clean_text(f"__SOURCE_PDF__:{pdf_file.name}\n\n{text}")
        out_file.write_text(cleaned, encoding="utf-8")
        logging.info("Wrote %s", out_file)


if __name__ == "__main__":
    main()
