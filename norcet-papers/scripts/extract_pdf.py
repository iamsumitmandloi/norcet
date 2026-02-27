#!/usr/bin/env python3
"""Extract and clean text from NORCET PDF papers year-wise.

Reads PDFs under raw_pdfs/{year}/ and writes cleaned year-wise text files to
extracted_text/{year}.txt.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF

MAX_HEADER_FOOTER_LINES = 3


class PdfYearExtractor:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.raw_pdfs_dir = root_dir / "raw_pdfs"
        self.extracted_dir = root_dir / "extracted_text"
        self.extracted_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_line(line: str) -> str:
        line = re.sub(r"\s+", " ", line).strip()
        return line

    @staticmethod
    def _is_noise_line(line: str) -> bool:
        if not line:
            return True

        compact = line.strip()
        lower = compact.lower()

        # Page labels / isolated page numbers.
        if re.fullmatch(r"(?:page\s*)?\d{1,4}(?:\s*/\s*\d{1,4})?", lower):
            return True

        # Common watermark-like text.
        if any(token in lower for token in ("memory based", "not for sale", "copyright", "www.")):
            return True

        # Decorative separators / short symbol lines.
        if re.fullmatch(r"[-_=~•·.\s]{3,}", compact):
            return True

        # Heuristic for all-caps/spaced watermark artifacts.
        alpha_chars = [c for c in compact if c.isalpha()]
        if alpha_chars:
            uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if uppercase_ratio > 0.9 and len(compact) <= 60 and compact.count(" ") > 4:
                return True

        return False

    def _collect_repeated_margin_lines(self, page_lines: list[list[str]]) -> set[str]:
        candidates: list[str] = []
        for lines in page_lines:
            if not lines:
                continue
            top = lines[:MAX_HEADER_FOOTER_LINES]
            bottom = lines[-MAX_HEADER_FOOTER_LINES:] if len(lines) > MAX_HEADER_FOOTER_LINES else []
            candidates.extend(top)
            candidates.extend(bottom)

        normalized = [self._normalize_line(line).lower() for line in candidates if self._normalize_line(line)]
        if not normalized:
            return set()

        counts = Counter(normalized)
        min_occurrences = max(2, int(len(page_lines) * 0.5))
        return {line for line, count in counts.items() if count >= min_occurrences}

    def _extract_pdf_clean_text(self, pdf_path: Path) -> str:
        doc = fitz.open(pdf_path)
        try:
            pages_raw_lines: list[list[str]] = []
            for page in doc:
                text = page.get_text("text")
                lines = [self._normalize_line(ln) for ln in text.splitlines()]
                lines = [ln for ln in lines if ln]
                pages_raw_lines.append(lines)

            repeated_margin_lines = self._collect_repeated_margin_lines(pages_raw_lines)

            cleaned_pages: list[str] = []
            for lines in pages_raw_lines:
                kept_lines: list[str] = []
                for line in lines:
                    norm_lower = self._normalize_line(line).lower()
                    if norm_lower in repeated_margin_lines:
                        continue
                    if self._is_noise_line(line):
                        continue
                    kept_lines.append(line)

                page_text = "\n".join(kept_lines).strip()
                if page_text:
                    cleaned_pages.append(page_text)

            return "\n\n".join(cleaned_pages).strip()
        finally:
            doc.close()

    def run(self) -> None:
        if not self.raw_pdfs_dir.exists():
            raise FileNotFoundError(f"Missing raw PDFs directory: {self.raw_pdfs_dir}")

        year_dirs = sorted(path for path in self.raw_pdfs_dir.iterdir() if path.is_dir())
        for year_dir in year_dirs:
            pdf_files = sorted(year_dir.glob("*.pdf"))
            if not pdf_files:
                continue

            blocks: list[str] = []
            for pdf_file in pdf_files:
                cleaned_text = self._extract_pdf_clean_text(pdf_file)
                if not cleaned_text:
                    continue

                blocks.append(f"### FILE: {pdf_file.name}\n\n{cleaned_text}")

            output_path = self.extracted_dir / f"{year_dir.name}.txt"
            output_path.write_text("\n\n".join(blocks).strip() + "\n", encoding="utf-8")
            print(f"Saved: {output_path.relative_to(self.root_dir)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract and clean year-wise NORCET PDF text")
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root containing raw_pdfs/ and extracted_text/",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    extractor = PdfYearExtractor(root_dir=args.root_dir)
    extractor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
