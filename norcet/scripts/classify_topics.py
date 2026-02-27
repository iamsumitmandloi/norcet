#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRUCTURED_DIR = ROOT / "structured_json"
KEYWORDS_FILE = STRUCTURED_DIR / "topic_keywords.json"


def load_keywords() -> dict:
    return json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))


def classify(text: str, keyword_map: dict) -> tuple[str, str, str]:
    normalized = text.lower()
    for subject, topics in keyword_map.items():
        for topic, subtopics in topics.items():
            for subtopic, keywords in subtopics.items():
                if any(keyword.lower() in normalized for keyword in keywords):
                    return subject, topic, subtopic
    return "Uncategorized", "Uncategorized", "Uncategorized"


def main() -> None:
    keyword_map = load_keywords()

    for json_file in sorted(STRUCTURED_DIR.glob("*.json")):
        if json_file.name == KEYWORDS_FILE.name:
            continue
        rows = json.loads(json_file.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            continue

        for row in rows:
            subject, topic, subtopic = classify(row.get("question_text", ""), keyword_map)
            row["subject"] = subject
            row["topic"] = topic
            row["subtopic"] = subtopic

        json_file.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
