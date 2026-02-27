#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw_pdfs"
LOGS_DIR = ROOT / "logs"
LINKS_FILE = Path(__file__).with_name("pdf_links.txt")
MANIFEST_FILE = LOGS_DIR / "download_manifest.json"
HASH_MANIFEST_FILE = LOGS_DIR / "hash_manifest.json"
FAIL_LOG_FILE = LOGS_DIR / "download_failures.log"

YEAR_RE = re.compile(r"(20\d{2})")
PDF_HREF_RE = re.compile(r"\.pdf($|\?)", re.IGNORECASE)


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def load_json(path: Path, default: dict) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_urls(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Input URL file not found: {path}")
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def detect_year(*candidates: str) -> str:
    for value in candidates:
        match = YEAR_RE.search(value)
        if match:
            return match.group(1)
    return "unknown"


def is_valid_pdf(data: bytes) -> bool:
    return len(data) > 1024 and data.startswith(b"%PDF")


def sha256_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or "document.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def extract_pdf_links_from_page(url: str, session: requests.Session) -> Iterable[str]:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "pdf" in content_type.lower() and is_valid_pdf(response.content):
        yield url
        return

    soup = BeautifulSoup(response.text, "html.parser")
    seen: set[str] = set()
    for tag in soup.select("a[href]"):
        href = tag.get("href", "").strip()
        if not href:
            continue
        abs_url = urljoin(url, href)
        if PDF_HREF_RE.search(abs_url) and abs_url not in seen:
            seen.add(abs_url)
            yield abs_url


def try_download_pdf(url: str, session: requests.Session) -> bytes:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    data = response.content
    if not is_valid_pdf(data):
        raise ValueError("Response is not a valid PDF")
    return data


def save_failure(message: str) -> None:
    with FAIL_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def main() -> None:
    setup_logging()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    manifest = load_json(MANIFEST_FILE, {"by_url": {}})
    hash_manifest = load_json(HASH_MANIFEST_FILE, {"by_hash": {}})

    urls = read_urls(LINKS_FILE)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (NORCET Pipeline Bot)"})

    downloaded = 0
    skipped = 0
    failed = 0

    for source_url in urls:
        if source_url in manifest["by_url"]:
            logging.info("Skip (already tracked): %s", source_url)
            skipped += 1
            continue

        candidate_links: list[str] = []
        if PDF_HREF_RE.search(source_url):
            candidate_links = [source_url]
        else:
            try:
                candidate_links = list(extract_pdf_links_from_page(source_url, session))
            except Exception as exc:  # noqa: BLE001
                failed += 1
                save_failure(f"{source_url}\tPAGE_FETCH_FAIL\t{exc}")
                continue

        if not candidate_links:
            failed += 1
            save_failure(f"{source_url}\tNO_PDF_LINK_FOUND")
            continue

        picked = False
        for pdf_url in candidate_links:
            try:
                data = try_download_pdf(pdf_url, session)
                file_hash = sha256_digest(data)
                if file_hash in hash_manifest["by_hash"]:
                    manifest["by_url"][source_url] = {
                        "status": "duplicate",
                        "matched_hash": file_hash,
                        "stored_as": hash_manifest["by_hash"][file_hash]["path"],
                        "source_pdf_url": pdf_url,
                    }
                    skipped += 1
                    picked = True
                    break

                year = detect_year(source_url, pdf_url)
                year_dir = RAW_DIR / year
                year_dir.mkdir(parents=True, exist_ok=True)
                filename = filename_from_url(pdf_url)
                out_path = year_dir / filename
                if out_path.exists():
                    out_path = year_dir / f"{out_path.stem}_{file_hash[:8]}.pdf"
                out_path.write_bytes(data)

                hash_manifest["by_hash"][file_hash] = {"path": str(out_path.relative_to(ROOT))}
                manifest["by_url"][source_url] = {
                    "status": "downloaded",
                    "hash": file_hash,
                    "path": str(out_path.relative_to(ROOT)),
                    "source_pdf_url": pdf_url,
                }
                downloaded += 1
                logging.info("Downloaded %s -> %s", pdf_url, out_path)
                picked = True
                break
            except Exception as exc:  # noqa: BLE001
                save_failure(f"{source_url}\tPDF_FETCH_FAIL\t{pdf_url}\t{exc}")

        if not picked:
            failed += 1
            manifest["by_url"][source_url] = {"status": "failed"}

    write_json(MANIFEST_FILE, manifest)
    write_json(HASH_MANIFEST_FILE, hash_manifest)
    logging.info("Done. downloaded=%s skipped=%s failed=%s", downloaded, skipped, failed)


if __name__ == "__main__":
    main()
