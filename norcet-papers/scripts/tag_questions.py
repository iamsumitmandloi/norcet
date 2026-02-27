#!/usr/bin/env python3
"""Tag parsed NORCET questions with subject/topic/subtopic labels.

Hybrid strategy:
1) Rule-based keyword scoring.
2) Optional LLM fallback when confidence is low.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_KEYWORDS: dict[str, dict[str, dict[str, list[str]]]] = {
    "Medical-Surgical Nursing": {
        "Emergency & Critical Care": {
            "Shock": ["shock", "hypovolemic", "cardiogenic", "septic", "anaphylactic"],
            "CPR": ["cpr", "compression", "ventilation", "resuscitation"],
        },
        "IV Therapy": {
            "Phlebitis": ["iv", "cannula", "phlebitis", "infiltration", "infusion"],
        },
    },
    "Pharmacology": {
        "Drug Safety": {
            "Dosage": ["drug", "dose", "dosage", "mg", "tablet", "injection"],
            "Adverse Effects": ["side effect", "adverse", "toxicity", "contraindication"],
        }
    },
    "Anatomy & Physiology": {
        "Human Anatomy": {
            "Bones": ["bone", "femur", "humerus", "vertebra"],
            "Neurovascular": ["artery", "vein", "nerve", "plexus"],
        }
    },
    "Obstetrics & Gynecology": {
        "Fetal Assessment": {
            "Fetal Position": ["fetal", "position", "lie", "station", "presentation"],
        }
    },
    "Neurology": {
        "Assessment": {
            "Glasgow Coma Scale": ["gcs", "glasgow", "coma", "score"],
        }
    },
}


@dataclass
class MatchResult:
    subject: str
    topic: str
    subtopic: str
    score: int


class QuestionTagger:
    def __init__(self, taxonomy: dict[str, dict[str, dict[str, list[str]]]], min_score: int, use_llm: bool) -> None:
        self.taxonomy = taxonomy
        self.min_score = min_score
        self.use_llm = use_llm

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()

    def _rule_based_tag(self, text: str) -> MatchResult:
        best = MatchResult(subject="Unknown", topic="Unknown", subtopic="Unknown", score=0)
        normalized = self._normalize(text)

        for subject, topics in self.taxonomy.items():
            for topic, subtopics in topics.items():
                for subtopic, keywords in subtopics.items():
                    score = 0
                    for kw in keywords:
                        if kw.lower() in normalized:
                            score += 1
                    if score > best.score:
                        best = MatchResult(subject=subject, topic=topic, subtopic=subtopic, score=score)
        return best

    def _llm_tag(self, text: str) -> MatchResult:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return MatchResult(subject="Unknown", topic="Unknown", subtopic="Unknown", score=0)

        prompt = (
            "Classify the nursing exam MCQ text into JSON with keys subject, topic, subtopic. "
            "Return ONLY minified JSON. Text: "
            f"{text[:2500]}"
        )
        payload = {
            "model": "gpt-4.1-mini",
            "input": prompt,
            "temperature": 0,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return MatchResult(subject="Unknown", topic="Unknown", subtopic="Unknown", score=0)

        output_text = ""
        for item in raw.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    output_text += content.get("text", "")
        try:
            parsed = json.loads(output_text.strip())
        except json.JSONDecodeError:
            return MatchResult(subject="Unknown", topic="Unknown", subtopic="Unknown", score=0)

        return MatchResult(
            subject=parsed.get("subject", "Unknown") or "Unknown",
            topic=parsed.get("topic", "Unknown") or "Unknown",
            subtopic=parsed.get("subtopic", "Unknown") or "Unknown",
            score=1,
        )

    @staticmethod
    def _question_text(question: dict[str, Any]) -> str:
        options = question.get("options", {})
        if isinstance(options, dict):
            option_values = " ".join(str(v) for v in options.values())
        elif isinstance(options, list):
            option_values = " ".join(str(v) for v in options)
        else:
            option_values = ""
        return " ".join(
            [
                str(question.get("question_text", "")),
                option_values,
                str(question.get("explanation", "")),
            ]
        )

    def tag_question(self, question: dict[str, Any]) -> dict[str, Any]:
        text = self._question_text(question)
        rule = self._rule_based_tag(text)
        method = "rule_based"

        if rule.score < self.min_score and self.use_llm:
            llm = self._llm_tag(text)
            if llm.subject != "Unknown":
                final = llm
                method = "llm"
            else:
                final = rule
        else:
            final = rule

        tagged = dict(question)
        tagged["subject"] = final.subject
        tagged["topic"] = final.topic
        tagged["subtopic"] = final.subtopic
        tagged["tagging_method"] = method
        tagged["tag_confidence"] = final.score
        return tagged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tag NORCET questions with subject/topic/subtopic")
    parser.add_argument("--root-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input-glob", default="structured_json/*.json")
    parser.add_argument("--output", default="structured_json/tagged_questions.json")
    parser.add_argument("--keyword-file", type=Path, help="Optional JSON taxonomy override")
    parser.add_argument("--min-score", type=int, default=2)
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM fallback for low-confidence matches")
    return parser.parse_args()


def load_taxonomy(keyword_file: Path | None) -> dict[str, dict[str, dict[str, list[str]]]]:
    if not keyword_file:
        return DEFAULT_KEYWORDS
    data = json.loads(keyword_file.read_text(encoding="utf-8"))
    return data


def extract_questions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if "questions" in payload and isinstance(payload["questions"], list):
        return payload["questions"]
    if "records" in payload and isinstance(payload["records"], list):
        return payload["records"]
    return []


def main() -> int:
    args = parse_args()
    root_dir = args.root_dir
    taxonomy = load_taxonomy(args.keyword_file)
    tagger = QuestionTagger(taxonomy=taxonomy, min_score=args.min_score, use_llm=args.use_llm)

    input_paths = sorted(Path(p) for p in glob.glob(str(root_dir / args.input_glob)))
    output_file = root_dir / args.output

    tagged_questions: list[dict[str, Any]] = []
    for path in input_paths:
        if path.resolve() == output_file.resolve():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for q in extract_questions(payload):
            tagged = tagger.tag_question(q)
            tagged["source_file"] = path.name
            tagged_questions.append(tagged)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_payload = {
        "count": len(tagged_questions),
        "questions": tagged_questions,
    }
    output_file.write_text(json.dumps(output_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(tagged_questions)} tagged questions -> {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
