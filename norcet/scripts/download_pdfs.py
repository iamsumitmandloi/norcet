#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw_pdfs"
LOGS_DIR = ROOT / "logs"
LINKS_FILE = Path(__file__).with_name("pdf_links.txt")
FAIL_LOG_FILE = LOGS_DIR / "download_failures.log"
MANIFEST_FILE = LOGS_DIR / "download_manifest.json"
HASH_MANIFEST_FILE = LOGS_DIR / "hash_manifest.json"

YEAR_RE = re.compile(r"(20\d{2})")


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_urls(path: Path) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def filename_from_url(url: str) -> str:
    parsed = urlparse(strip_fragment(url))
    name = Path(parsed.path).name or "document.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def detect_year(url: str, filename: str) -> str:
    for candidate in (filename, url):
        m = YEAR_RE.search(candidate)
        if m:
            return m.group(1)
    return "unknown"


def is_pdf_bytes(data: bytes) -> bool:
    return data.startswith(b"%PDF") and len(data) > 1000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def log_failure(source_url: str, reason: str) -> None:
    with FAIL_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{source_url}\t{reason}\n")


def main() -> None:
    setup_logging()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    manifest = load_json(MANIFEST_FILE, {"by_url": {}})
    hash_manifest = load_json(HASH_MANIFEST_FILE, {"by_hash": {}})

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (NORCET PDF Downloader)"})

    for source_url in read_urls(LINKS_FILE):
        clean_url = strip_fragment(source_url)
        if clean_url in manifest["by_url"]:
            logging.info("Skip known URL: %s", clean_url)
            continue

        try:
            response = session.get(clean_url, timeout=90)
            response.raise_for_status()
            data = response.content
            if not is_pdf_bytes(data):
                raise ValueError("Not a valid PDF response")

            digest = sha256(data)
            if digest in hash_manifest["by_hash"]:
                manifest["by_url"][clean_url] = {
                    "status": "duplicate",
                    "matched_hash": digest,
                    "stored_as": hash_manifest["by_hash"][digest]["path"],
                }
                logging.info("Skip duplicate by hash: %s", clean_url)
                continue

            filename = filename_from_url(clean_url)
            year = detect_year(clean_url, filename)
            out_dir = RAW_DIR / year
            out_dir.mkdir(parents=True, exist_ok=True)

            out_path = out_dir / filename
            if out_path.exists():
                out_path = out_dir / f"{out_path.stem}_{digest[:8]}.pdf"
            out_path.write_bytes(data)

            rel = str(out_path.relative_to(ROOT))
            hash_manifest["by_hash"][digest] = {"path": rel}
            manifest["by_url"][clean_url] = {
                "status": "downloaded",
                "hash": digest,
                "path": rel,
            }
            logging.info("Downloaded %s -> %s", clean_url, out_path)
        except Exception as exc:  # noqa: BLE001
            manifest["by_url"][clean_url] = {"status": "failed", "error": str(exc)}
            log_failure(clean_url, str(exc))
            logging.error("Failed %s (%s)", clean_url, exc)

    write_json(MANIFEST_FILE, manifest)
    write_json(HASH_MANIFEST_FILE, hash_manifest)


if __name__ == "__main__":
    main()
