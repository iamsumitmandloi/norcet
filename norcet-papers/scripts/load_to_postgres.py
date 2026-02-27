#!/usr/bin/env python3
"""Load finalized NORCET questions into PostgreSQL with upsert support."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import psycopg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load NORCET dataset to PostgreSQL")
    parser.add_argument("--root-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input", default="structured_json/final_questions.json")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args()


def q_hash(question: dict) -> str:
    key = {
        "year": question.get("year"),
        "question_text": question.get("question_text", ""),
        "options": question.get("options", {}),
    }
    return hashlib.sha256(json.dumps(key, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def chunks(items: list[dict], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main() -> int:
    args = parse_args()
    in_file = args.root_dir / args.input
    payload = json.loads(in_file.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    sql = """
    INSERT INTO questions (
      question_hash, year, subject, topic, subtopic, question_text,
      option_a, option_b, option_c, option_d, correct_answer,
      explanation, source_pdf, source_file
    ) VALUES (
      %(question_hash)s, %(year)s, %(subject)s, %(topic)s, %(subtopic)s, %(question_text)s,
      %(option_a)s, %(option_b)s, %(option_c)s, %(option_d)s, %(correct_answer)s,
      %(explanation)s, %(source_pdf)s, %(source_file)s
    )
    ON CONFLICT (question_hash) DO UPDATE SET
      subject = EXCLUDED.subject,
      topic = EXCLUDED.topic,
      subtopic = EXCLUDED.subtopic,
      correct_answer = EXCLUDED.correct_answer,
      explanation = EXCLUDED.explanation,
      source_pdf = EXCLUDED.source_pdf,
      source_file = EXCLUDED.source_file;
    """

    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            total = 0
            for batch in chunks(questions, args.batch_size):
                rows = []
                for q in batch:
                    options = q.get("options", {})
                    rows.append(
                        {
                            "question_hash": q_hash(q),
                            "year": q.get("year"),
                            "subject": q.get("subject", "Unknown"),
                            "topic": q.get("topic", "Unknown"),
                            "subtopic": q.get("subtopic", "Unknown"),
                            "question_text": q.get("question_text", ""),
                            "option_a": options.get("A", ""),
                            "option_b": options.get("B", ""),
                            "option_c": options.get("C", ""),
                            "option_d": options.get("D", ""),
                            "correct_answer": q.get("correct_answer", "A"),
                            "explanation": q.get("explanation", ""),
                            "source_pdf": q.get("source_pdf", ""),
                            "source_file": q.get("source_file", ""),
                        }
                    )

                cur.executemany(sql, rows)
                total += len(rows)
            conn.commit()

    print(f"Upserted {total} question rows into PostgreSQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
