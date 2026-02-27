# NORCET Papers Repository

Phase 1 is now set up to support **AIIMS NORCET paper collection from 2012 to latest** (with active known unofficial availability from 2020 onward).

## Structure

```text
norcet-papers/
├── raw_pdfs/
│   ├── 2012/ ... 2024/
│   └── unknown/
├── extracted_text/
├── structured_json/
│   └── sample_memory_mcqs.json
├── logs/
└── scripts/
    ├── downloader.py
    └── urls.txt
```

## Install dependencies

```bash
python3 -m pip install -r norcet-papers/requirements.txt
```

## Add paper links

Put all paper/archive links in `norcet-papers/scripts/urls.txt` (one URL per line).

## Download papers

```bash
python3 norcet-papers/scripts/downloader.py --url-file norcet-papers/scripts/urls.txt
```

Optional range override:

```bash
python3 norcet-papers/scripts/downloader.py --url-file norcet-papers/scripts/urls.txt --min-year 2012 --max-year 2026
```

## Downloader behavior

- Accepts direct PDF links and HTML archive pages.
- Parses first PDF link from page when direct PDF is not provided.
- Detects year from URL, headers, and page content.
- Saves files in `raw_pdfs/{year}/`.
- Prevents duplicates via:
  - `logs/download_manifest.json` (URL -> file)
  - `logs/hash_manifest.json` (SHA256 -> file)
- Logs failed links in `logs/download_failures.log`.

## Included sample extracted MCQs

`structured_json/sample_memory_mcqs.json` contains normalized sample records for 2020–2024 with fields ready for filtering:

- `year`
- `subject`
- `topic`
- `subtopic`
- `question_text`
- `options`
- `correct_answer`
- `explanation`
- `source`

This file is a starter dataset created from the provided memory-based examples and can be expanded once full PDFs are downloaded and parsed.


## Parse extracted text into structured MCQs (Phase 3)

```bash
python3 norcet-papers/scripts/parse_mcq.py --year 2022
```

Optional metadata defaults (used when subject/topic/subtopic are not found in extracted text):

```bash
python3 norcet-papers/scripts/parse_mcq.py --year 2022 --subject "Medical Surgical Nursing" --topic "Cardiology" --subtopic "Shock"
```

Output is written to `structured_json/{year}.json`.


## Tag structured questions (Phase 4)

Run the hybrid tagging module to assign `subject`, `topic`, and `subtopic` labels from question content:

```bash
python3 norcet-papers/scripts/tag_questions.py
```

By default it uses rule-based keyword matching and writes:

- `structured_json/tagged_questions.json`

Optional LLM fallback (used only when rule score is below threshold):

```bash
OPENAI_API_KEY=... python3 norcet-papers/scripts/tag_questions.py --use-llm --min-score 2
```

Optional custom keyword taxonomy JSON:

```bash
python3 norcet-papers/scripts/tag_questions.py --keyword-file norcet-papers/structured_json/topic_keywords.json
```


## Query API (Phase 6)

Start API server:

```bash
uvicorn scripts.query_api:app --app-dir norcet-papers --host 0.0.0.0 --port 8000
```

Available filters on `GET /questions`:

- Year-wise: `GET /questions?year=2022`
- Subject-wise: `GET /questions?subject=Anatomy`
- Topic-wise: `GET /questions?topic=Shock`
- Subtopic-wise: `GET /questions?subtopic=Hypovolemic%20Shock`
- Mixed filter: `GET /questions?year=2022&subject=Pharmacology`

All filters are optional and can be combined. Text filters are case-insensitive exact matches.
