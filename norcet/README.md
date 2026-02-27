# NORCET Data Pipeline

## Setup

```bash
pip install -r requirements.txt
```

## Run pipeline

```bash
python scripts/download_pdfs.py
python scripts/extract_text.py
python scripts/parse_mcq.py
python scripts/classify_topics.py
```

## Output

- `raw_pdfs/` year-wise PDF storage (generated locally)
- `extracted_text/` cleaned text files (generated locally)
- `structured_json/` year-wise structured question JSON
- `scripts/schema.sql` database schema for import

## Input URLs

Populate or edit:

- `scripts/pdf_links.txt`

## Git tracking policy

Generated binaries and runtime logs are ignored from git:

- `raw_pdfs/**/*.pdf`
- `extracted_text/*.txt`
- `logs/*.json`
- `logs/download_failures.log`

Directory placeholders are committed via `.gitkeep` files.
