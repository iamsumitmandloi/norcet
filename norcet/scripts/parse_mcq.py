#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "extracted_text"
OUT_DIR = ROOT / "structured_json"

QUESTION_START_RE = re.compile(r"^\s*(?:Q(?:uestion)?\s*)?(\d{1,3})[\).:-]\s*(.+)?$", re.IGNORECASE)
OPTION_RE = re.compile(r"^\s*[\(\[]?([A-Da-d])[\)\].:-]\s*(.+)?$")
ANSWER_INLINE_RE = re.compile(r"(?:Ans(?:wer)?\s*[:.-]?\s*)([A-D])", re.IGNORECASE)
ANSWER_KEY_ROW_RE = re.compile(r"^(\d{1,3})\s*[-:.)]\s*([A-D])$", re.IGNORECASE)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_file(path: Path) -> tuple[str, list[dict]]:
    year = path.stem.split("_", 1)[0]
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    source_pdf = "unknown.pdf"
    if lines and lines[0].startswith("__SOURCE_PDF__:"):
        source_pdf = lines[0].split(":", 1)[1].strip()
        lines = lines[1:]

    answer_key: dict[int, str] = {}
    for ln in lines:
        m = ANSWER_KEY_ROW_RE.match(ln.strip())
        if m:
            answer_key[int(m.group(1))] = m.group(2).upper()

    questions: list[dict] = []
    current: dict | None = None
    current_opt: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        qmatch = QUESTION_START_RE.match(line)
        if qmatch:
            if current and all(k in current["options"] for k in ["A", "B", "C", "D"]):
                questions.append(current)
            qnum = int(qmatch.group(1))
            qtext = qmatch.group(2) or ""
            current = {
                "qnum": qnum,
                "question_text": normalize_space(qtext),
                "options": {},
                "correct_answer": None,
            }
            current_opt = None
            continue

        if current is None:
            continue

        omatch = OPTION_RE.match(line)
        if omatch:
            opt = omatch.group(1).upper()
            txt = normalize_space(omatch.group(2) or "")
            current["options"][opt] = txt
            current_opt = opt
            continue

        inline_ans = ANSWER_INLINE_RE.search(line)
        if inline_ans:
            current["correct_answer"] = inline_ans.group(1).upper()
            continue

        if current_opt:
            current["options"][current_opt] = normalize_space(current["options"][current_opt] + " " + line)
        else:
            current["question_text"] = normalize_space(current["question_text"] + " " + line)

    if current and all(k in current["options"] for k in ["A", "B", "C", "D"]):
        questions.append(current)

    output: list[dict] = []
    seen: set[str] = set()
    for q in questions:
        answer = q["correct_answer"] or answer_key.get(q["qnum"])
        dedupe_key = "|".join([
            normalize_space(q["question_text"]).lower(),
            normalize_space(q["options"].get("A", "")).lower(),
            normalize_space(q["options"].get("B", "")).lower(),
            normalize_space(q["options"].get("C", "")).lower(),
            normalize_space(q["options"].get("D", "")).lower(),
        ])
        h = hashlib.sha256(dedupe_key.encode()).hexdigest()
        if h in seen:
            continue
        seen.add(h)

        output.append({
            "question_id": str(uuid.uuid4()),
            "year": int(year) if year.isdigit() else None,
            "subject": None,
            "topic": None,
            "subtopic": None,
            "question_text": q["question_text"],
            "options": {
                "A": q["options"].get("A"),
                "B": q["options"].get("B"),
                "C": q["options"].get("C"),
                "D": q["options"].get("D"),
            },
            "correct_answer": answer if answer in {"A", "B", "C", "D"} else None,
            "explanation": None,
            "source_pdf": source_pdf,
        })

    return year, output


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict]] = defaultdict(list)

    for txt in sorted(TEXT_DIR.glob("*.txt")):
        year, rows = parse_file(txt)
        grouped[year].extend(rows)

    for year, items in grouped.items():
        out_path = OUT_DIR / f"{year}.json"
        out_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
