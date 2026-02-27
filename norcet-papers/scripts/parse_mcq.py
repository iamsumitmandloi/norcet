#!/usr/bin/env python3
"""Parse extracted NORCET text into structured MCQ JSON."""

from __future__ import annotations

import argparse
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

QUESTION_Q_RE = re.compile(r"^\s*q(?:uestion)?\s*(\d{1,3})\s*[\).:-]\s*(.*)$", re.IGNORECASE)
QUESTION_NUM_RE = re.compile(r"^\s*(\d{1,3})\s*[\.:-]\s*(.*)$")
OPTION_ALPHA_RE = re.compile(r"^\s*[\(\[]?([A-D])[\)\].:-]\s*(.*)$", re.IGNORECASE)
OPTION_NUM_RE = re.compile(r"^\s*([1-4])[\).:-]\s*(.*)$")
INLINE_OPTIONS_RE = re.compile(r"[\(\[]?([A-D])[\)\]]\s*[:.-]?\s*(.*?)(?=(?:\s+[\(\[]?[A-D][\)\]])|$)", re.IGNORECASE)
ANSWER_RE = re.compile(
    r"(?:^|\b)(?:ans(?:wer)?|correct\s*answer|key)\s*[:\-]?\s*(?:option\s*)?[\(\[]?([A-D1-4])[\)\]]?\b",
    re.IGNORECASE,
)
EXPLANATION_RE = re.compile(r"^\s*(?:explanation|rationale)\s*[:\-]\s*(.*)$", re.IGNORECASE)
SUBJECT_RE = re.compile(r"^\s*subject\s*[:\-]\s*(.+)$", re.IGNORECASE)
TOPIC_RE = re.compile(r"^\s*topic\s*[:\-]\s*(.+)$", re.IGNORECASE)
SUBTOPIC_RE = re.compile(r"^\s*subtopic\s*[:\-]\s*(.+)$", re.IGNORECASE)

OPTION_MAP = {"1": "A", "2": "B", "3": "C", "4": "D"}
NOISE_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"\b(?:telegram|whatsapp|instagram|facebook|youtube)\b", re.IGNORECASE),
    re.compile(r"\b(?:subscribe|follow us|join (?:our )?channel|download app)\b", re.IGNORECASE),
    re.compile(r"\b(?:copyright|all rights reserved|not for sale|memory based)\b", re.IGNORECASE),
    re.compile(r"^\s*page\s*\d+(?:\s*/\s*\d+)?\s*$", re.IGNORECASE),
)


@dataclass
class ParseDefaults:
    year: int
    subject: str
    topic: str
    subtopic: str


class McqParser:
    def __init__(self, defaults: ParseDefaults) -> None:
        self.defaults = defaults

    @staticmethod
    def _normalize_line(line: str) -> str:
        line = line.replace("\u00a0", " ")
        return re.sub(r"\s+", " ", line).strip()

    def _is_noise_line(self, line: str) -> bool:
        if not line:
            return True
        if re.fullmatch(r"[-_=~.•·\s]{3,}", line):
            return True
        return any(pattern.search(line) for pattern in NOISE_PATTERNS)

    def _clean_lines(self, text: str) -> list[str]:
        lines = [self._normalize_line(ln) for ln in text.splitlines()]
        return [ln for ln in lines if not self._is_noise_line(ln)]

    @staticmethod
    def _extract_sections(raw_text: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        parts = re.split(r"^### FILE:\s*(.+)$", raw_text, flags=re.MULTILINE)
        if len(parts) <= 1:
            return [("unknown_source.pdf", raw_text)]
        for i in range(1, len(parts), 2):
            source = parts[i].strip()
            body = parts[i + 1] if i + 1 < len(parts) else ""
            sections.append((source, body))
        return sections

    def _split_question_blocks(self, lines: Iterable[str]) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            if QUESTION_Q_RE.match(line) or QUESTION_NUM_RE.match(line):
                if current:
                    blocks.append(current)
                current = [line]
            elif current:
                current.append(line)
        if current:
            blocks.append(current)
        return blocks

    @staticmethod
    def _detect_metadata(lines: list[str], defaults: ParseDefaults) -> tuple[str, str, str]:
        subject, topic, subtopic = defaults.subject, defaults.topic, defaults.subtopic
        for line in lines:
            if match := SUBJECT_RE.match(line):
                subject = match.group(1).strip()
            elif match := TOPIC_RE.match(line):
                topic = match.group(1).strip()
            elif match := SUBTOPIC_RE.match(line):
                subtopic = match.group(1).strip()
        return subject, topic, subtopic

    def _parse_question_block(
        self,
        block: list[str],
        source_pdf: str,
        subject: str,
        topic: str,
        subtopic: str,
    ) -> dict | None:
        head_match = QUESTION_Q_RE.match(block[0]) or QUESTION_NUM_RE.match(block[0])
        if not head_match:
            return None

        question_bits: list[str] = [head_match.group(2).strip()] if head_match.group(2).strip() else []
        options: dict[str, str] = {}
        current_option: str | None = None
        explanation_parts: list[str] = []
        answer: str = ""

        for raw_line in block[1:]:
            line = raw_line.strip()
            if not line:
                continue

            if match := ANSWER_RE.search(line):
                raw_answer = match.group(1).upper()
                answer = OPTION_MAP.get(raw_answer, raw_answer)
                continue

            if match := EXPLANATION_RE.match(line):
                explanation_parts.append(match.group(1).strip())
                current_option = None
                continue

            if explanation_parts:
                explanation_parts.append(line)
                continue

            if alpha := OPTION_ALPHA_RE.match(line):
                key = alpha.group(1).upper()
                options[key] = alpha.group(2).strip()
                current_option = key
                continue

            if numeric := OPTION_NUM_RE.match(line):
                key = OPTION_MAP[numeric.group(1)]
                options[key] = numeric.group(2).strip()
                current_option = key
                continue

            inline_found = list(INLINE_OPTIONS_RE.finditer(line))
            if inline_found and len(inline_found) >= 2:
                for m in inline_found:
                    options[m.group(1).upper()] = m.group(2).strip(" ;")
                current_option = None
                continue

            if current_option and len(options) <= 4:
                options[current_option] = f"{options[current_option]} {line}".strip()
            else:
                question_bits.append(line)

        if len(options) < 2:
            return None

        ordered_options = {k: options[k] for k in ("A", "B", "C", "D") if k in options}
        return {
            "question_id": str(uuid.uuid4()),
            "year": self.defaults.year,
            "subject": subject,
            "topic": topic,
            "subtopic": subtopic,
            "question_text": " ".join(question_bits).strip(),
            "options": ordered_options,
            "correct_answer": answer,
            "explanation": " ".join(explanation_parts).strip() if explanation_parts else "",
            "source_pdf": source_pdf,
        }

    def parse(self, raw_text: str) -> list[dict]:
        records: list[dict] = []
        for source_pdf, body in self._extract_sections(raw_text):
            lines = self._clean_lines(body)
            subject, topic, subtopic = self._detect_metadata(lines, self.defaults)
            blocks = self._split_question_blocks(lines)
            for block in blocks:
                parsed = self._parse_question_block(block, source_pdf, subject, topic, subtopic)
                if parsed:
                    records.append(parsed)
        return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse extracted NORCET text into structured MCQ JSON")
    parser.add_argument("--root-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--year", type=int, required=True, help="Year to parse (maps to extracted_text/{year}.txt)")
    parser.add_argument("--subject", default="Unknown")
    parser.add_argument("--topic", default="Unknown")
    parser.add_argument("--subtopic", default="Unknown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    extracted_file = args.root_dir / "extracted_text" / f"{args.year}.txt"
    output_dir = args.root_dir / "structured_json"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not extracted_file.exists():
        raise FileNotFoundError(f"Missing extracted text file: {extracted_file}")

    parser = McqParser(
        ParseDefaults(
            year=args.year,
            subject=args.subject,
            topic=args.topic,
            subtopic=args.subtopic,
        )
    )

    records = parser.parse(extracted_file.read_text(encoding="utf-8"))
    out_file = output_dir / f"{args.year}.json"
    payload = {"year": args.year, "count": len(records), "questions": records}
    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(records)} MCQs -> {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
