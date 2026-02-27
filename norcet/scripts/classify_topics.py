#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRUCTURED_DIR = ROOT / "structured_json"
KEYWORDS_FILE = STRUCTURED_DIR / "topic_keywords.json"

DEFAULT_KEYWORDS = {
    "Medical Surgical Nursing": {
        "Cardiology": {
            "Shock": ["shock", "hypovolemic", "cardiogenic"],
            "Hypertension": ["hypertension", "blood pressure", "antihypertensive"],
        },
        "Respiratory": {
            "Asthma": ["asthma", "bronchodilator", "wheeze"],
        },
    },
    "Pharmacology": {
        "Drug Safety": {
            "Adverse Effects": ["adverse effect", "toxicity", "dose", "contraindication"],
        }
    },
}


def ensure_keywords() -> dict:
    if not KEYWORDS_FILE.exists():
        KEYWORDS_FILE.write_text(json.dumps(DEFAULT_KEYWORDS, indent=2), encoding="utf-8")
        return DEFAULT_KEYWORDS
    return json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))


def classify(question_text: str, kw_map: dict) -> tuple[str, str | None, str | None]:
    text = question_text.lower()
    for subject, topics in kw_map.items():
        for topic, subtopics in topics.items():
            for subtopic, keywords in subtopics.items():
                if any(k.lower() in text for k in keywords):
                    return subject, topic, subtopic
    return "Uncategorized", None, None


def main() -> None:
    kw_map = ensure_keywords()

    for path in sorted(STRUCTURED_DIR.glob("*.json")):
        if path.name == KEYWORDS_FILE.name:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            continue

        for row in data:
            subject, topic, subtopic = classify(row.get("question_text", ""), kw_map)
            row["subject"] = subject
            row["topic"] = topic
            row["subtopic"] = subtopic

        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
