#!/usr/bin/env python3
"""Validate quality rules for finalized NORCET dataset."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate NORCET dataset quality")
    parser.add_argument("--root-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input", default="structured_json/final_questions.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads((args.root_dir / args.input).read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    problems: list[str] = []
    signatures: set[tuple] = set()
    year_counts = Counter()

    for idx, q in enumerate(questions, start=1):
        year = q.get("year")
        year_counts[year] += 1

        options = q.get("options", {})
        if not isinstance(options, dict):
            problems.append(f"Q{idx}: options must be an object")
            continue

        for key in ("A", "B", "C", "D"):
            if key not in options or not str(options[key]).strip():
                problems.append(f"Q{idx}: missing option {key}")

        answer = q.get("correct_answer")
        if answer not in {"A", "B", "C", "D"}:
            problems.append(f"Q{idx}: invalid correct_answer '{answer}'")

        signature = (year, str(q.get("question_text", "")).strip(), json.dumps(options, sort_keys=True, ensure_ascii=False))
        if signature in signatures:
            problems.append(f"Q{idx}: duplicate question detected")
        signatures.add(signature)

    print("Year-wise question count:")
    for year, count in sorted(year_counts.items(), key=lambda x: (x[0] is None, x[0])):
        print(f"  {year}: {count}")

    if problems:
        print("Validation FAILED:")
        for issue in problems[:30]:
            print(f" - {issue}")
        print(f"Total issues: {len(problems)}")
        return 1

    print(f"Validation PASSED for {len(questions)} questions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
