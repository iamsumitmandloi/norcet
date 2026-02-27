#!/usr/bin/env python3
"""Phase 6 query API for NORCET questions.

Run locally:
    uvicorn scripts.query_api:app --app-dir norcet-papers --reload --port 8000
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query

BASE_DIR = Path(__file__).resolve().parents[1]
STRUCTURED_JSON_DIR = BASE_DIR / "structured_json"

app = FastAPI(title="NORCET Question Query API", version="0.1.0")


def _read_questions_from_file(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        return [q for q in payload["questions"] if isinstance(q, dict)]
    if isinstance(payload, list):
        return [q for q in payload if isinstance(q, dict)]
    return []


def load_question_bank() -> list[dict[str, Any]]:
    """Load questions from tagged output first; fallback to all structured JSON files."""
    tagged_file = STRUCTURED_JSON_DIR / "tagged_questions.json"
    if tagged_file.exists():
        return _read_questions_from_file(tagged_file)

    questions: list[dict[str, Any]] = []
    for file_path in sorted(STRUCTURED_JSON_DIR.glob("*.json")):
        questions.extend(_read_questions_from_file(file_path))
    return questions


def _matches_string_filter(value: Any, expected: str) -> bool:
    if value is None:
        return False
    return str(value).strip().casefold() == expected.strip().casefold()


def apply_filters(
    questions: list[dict[str, Any]],
    year: int | None = None,
    subject: str | None = None,
    topic: str | None = None,
    subtopic: str | None = None,
) -> list[dict[str, Any]]:
    filtered = questions

    if year is not None:
        filtered = [q for q in filtered if q.get("year") == year]

    if subject:
        filtered = [q for q in filtered if _matches_string_filter(q.get("subject"), subject)]

    if topic:
        filtered = [q for q in filtered if _matches_string_filter(q.get("topic"), topic)]

    if subtopic:
        filtered = [q for q in filtered if _matches_string_filter(q.get("subtopic"), subtopic)]

    return filtered


@app.get("/questions")
def get_questions(
    year: int | None = Query(default=None, description="Filter by exam year"),
    subject: str | None = Query(default=None, description="Filter by subject name"),
    topic: str | None = Query(default=None, description="Filter by topic name"),
    subtopic: str | None = Query(default=None, description="Filter by subtopic name"),
) -> dict[str, Any]:
    questions = load_question_bank()
    filtered = apply_filters(questions, year=year, subject=subject, topic=topic, subtopic=subtopic)

    return {
        "count": len(filtered),
        "filters": {
            "year": year,
            "subject": subject,
            "topic": topic,
            "subtopic": subtopic,
        },
        "questions": filtered,
    }
