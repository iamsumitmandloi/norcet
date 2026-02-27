#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "extracted_text"
OUT_DIR = ROOT / "structured_json"

QUESTION_RE = re.compile(r"^(?:Q(?:uestion)?\s*)?(\d{1,3})[\).:-]\s*(.*)$", re.IGNORECASE)
OPTION_RE = re.compile(r"^[\(\[]?([A-D])[\)\].:-]\s*(.*)$", re.IGNORECASE)


def parse_questions(lines: list[str], year: str, source_pdf: str) -> list[dict]:
    rows: list[dict] = []
    current: dict | None = None
    current_opt: str | None = None

    for raw in lines:
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue

        q = QUESTION_RE.match(line)
        if q:
            if current and len(current["options"]) == 4:
                rows.append(current)
            current = {
                "year": int(year) if year.isdigit() else None,
                "question_number": int(q.group(1)),
                "question_text": q.group(2).strip(),
                "options": {},
                "correct_answer": None,
                "subject": None,
                "topic": None,
                "subtopic": None,
                "source_pdf": source_pdf,
            }
            current_opt = None
            continue

        if current is None:
            continue

        o = OPTION_RE.match(line)
        if o:
            current_opt = o.group(1).upper()
            current["options"][current_opt] = o.group(2).strip()
            continue

        if current_opt:
            current["options"][current_opt] = f"{current['options'][current_opt]} {line}".strip()
        else:
            current["question_text"] = f"{current['question_text']} {line}".strip()

    if current and len(current["options"]) == 4:
        rows.append(current)

    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict]] = defaultdict(list)

    for txt_file in sorted(TEXT_DIR.glob("*.txt")):
        year = txt_file.stem.split("_", 1)[0]
        lines = txt_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        source_pdf = "unknown.pdf"
        if lines and lines[0].startswith("__SOURCE_PDF__:"):
            source_pdf = lines[0].split(":", 1)[1].strip()
            lines = lines[1:]

        grouped[year].extend(parse_questions(lines, year, source_pdf))

    for year, questions in grouped.items():
        out_path = OUT_DIR / f"{year}.json"
        out_path.write_text(json.dumps(questions, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
