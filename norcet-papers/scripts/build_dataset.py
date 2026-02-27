#!/usr/bin/env python3
"""Build a clean NORCET dataset from parsed/tagged JSON files.

Rules enforced:
- no duplicate questions per year/text/options combination
- preserve original wording/options
- keep correct answer integrity
- emit year-wise counts for validation
"""

from __future__ import annotations

import argparse
import glob
import json
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build unified NORCET question dataset")
    parser.add_argument("--root-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input-glob", default="structured_json/*.json")
    parser.add_argument("--output", default="structured_json/final_questions.json")
    parser.add_argument("--report", default="structured_json/year_counts.json")
    return parser.parse_args()


def extract_questions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("questions"), list):
        return payload["questions"]
    if isinstance(payload.get("records"), list):
        return payload["records"]
    return []


def normalize_options(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        out = {k: str(v).strip() for k, v in raw.items() if str(v).strip()}
        return {k: out[k] for k in ("A", "B", "C", "D") if k in out}
    if isinstance(raw, list):
        options = [str(v).strip() for v in raw]
        mapped = {}
        for i, key in enumerate(("A", "B", "C", "D")):
            if i < len(options) and options[i]:
                mapped[key] = options[i]
        return mapped
    return {}


def stable_key(question: dict[str, Any]) -> str:
    payload = {
        "year": question.get("year"),
        "question_text": str(question.get("question_text", "")).strip(),
        "options": normalize_options(question.get("options", {})),
    }
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def normalize_answer(answer: Any, options: dict[str, str]) -> str:
    raw = str(answer or "").strip()
    if raw in {"A", "B", "C", "D"}:
        return raw
    for key, value in options.items():
        if raw and raw.casefold() == str(value).strip().casefold():
            return key
    return ""


def normalize_question(q: dict[str, Any]) -> dict[str, Any] | None:
    options = normalize_options(q.get("options"))
    if len(options) < 2:
        return None

    normalized = dict(q)
    normalized["options"] = options
    normalized["question_text"] = str(q.get("question_text", "")).strip()
    normalized["correct_answer"] = normalize_answer(q.get("correct_answer"), options)
    normalized["year"] = int(q.get("year")) if q.get("year") is not None else None
    return normalized


def main() -> int:
    args = parse_args()
    root = args.root_dir
    input_paths = sorted(Path(p) for p in glob.glob(str(root / args.input_glob)))
    output_path = root / args.output

    all_questions: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates = 0

    for path in input_paths:
        if path.resolve() == output_path.resolve():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for question in extract_questions(payload):
            normalized = normalize_question(question)
            if not normalized:
                continue
            key = stable_key(normalized)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            all_questions.append(normalized)

    year_counts = Counter(q.get("year") for q in all_questions if q.get("year") is not None)

    output_payload = {
        "count": len(all_questions),
        "duplicates_removed": duplicates,
        "questions": all_questions,
    }
    output_path.write_text(json.dumps(output_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report_path = root / args.report
    report_payload = {
        "total_questions": len(all_questions),
        "year_counts": {str(k): v for k, v in sorted(year_counts.items())},
    }
    report_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Built dataset with {len(all_questions)} questions ({duplicates} duplicates removed)")
    print(f"Saved: {output_path}")
    print(f"Saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
