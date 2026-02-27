#!/usr/bin/env python3
"""Download NORCET PDFs into year-wise folders.

Features:
- Accept URLs from CLI arguments and/or a text file.
- Detect year from URL, headers, or HTML page content.
- Download PDFs into raw_pdfs/{year}/.
- Skip duplicates using URL and content-hash manifests.
- Log failures to logs/download_failures.log.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; NORCET-Downloader/1.1)"


@dataclass
class DownloadResult:
    url: str
    status: str
    message: str
    saved_path: str | None = None


class NorcetDownloader:
    def __init__(self, root_dir: Path, min_year: int = 2012, max_year: int | None = None) -> None:
        self.root_dir = root_dir
        self.raw_pdfs = root_dir / "raw_pdfs"
        self.logs_dir = root_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.min_year = min_year
        self.max_year = max_year or datetime.now().year
        self.allowed_years = {str(y) for y in range(self.min_year, self.max_year + 1)}

        self.url_manifest_path = self.logs_dir / "download_manifest.json"
        self.hash_manifest_path = self.logs_dir / "hash_manifest.json"
        self.failure_log_path = self.logs_dir / "download_failures.log"

        self.url_manifest = self._load_json(self.url_manifest_path)
        self.hash_manifest = self._load_json(self.hash_manifest_path)

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    @staticmethod
    def _load_json(path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _save_json(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _log_failure(self, result: DownloadResult) -> None:
        with self.failure_log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{result.url}\t{result.message}\n")

    def _extract_year(self, text: str) -> str | None:
        for year in re.findall(r"\b(20\d{2})\b", text):
            if year in self.allowed_years:
                return year
        return None

    @staticmethod
    def _is_pdf_response(response: requests.Response) -> bool:
        ctype = response.headers.get("Content-Type", "").lower()
        return "application/pdf" in ctype or response.url.lower().endswith(".pdf")

    @staticmethod
    def _safe_filename(candidate: str) -> str:
        cleaned = re.sub(r"[\\/:*?\"<>|]", "_", candidate).strip()
        return cleaned or "norcet_paper.pdf"

    def _filename_from_response(self, response: requests.Response, fallback_url: str) -> str:
        content_disposition = response.headers.get("Content-Disposition", "")
        name_match = re.search(r'filename="?([^\";]+)"?', content_disposition)
        if name_match:
            candidate = name_match.group(1)
        else:
            path = unquote(urlparse(fallback_url).path)
            candidate = Path(path).name or "norcet_paper.pdf"

        if not candidate.lower().endswith(".pdf"):
            candidate += ".pdf"
        return self._safe_filename(candidate)

    @staticmethod
    def _sha256_bytes(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _detect_year(self, url: str, response: requests.Response, content: bytes) -> str | None:
        year = self._extract_year(url)
        if year:
            return year

        content_disposition = response.headers.get("Content-Disposition", "")
        year = self._extract_year(content_disposition)
        if year:
            return year

        if "text/html" in response.headers.get("Content-Type", "").lower():
            soup = BeautifulSoup(content, "html.parser")
            text_blob = " ".join(
                filter(None, [soup.title.string if soup.title else "", soup.get_text(" ", strip=True)])
            )
            year = self._extract_year(text_blob)
            if year:
                return year

            for anchor in soup.find_all("a", href=True):
                year = self._extract_year(anchor.get("href", ""))
                if year:
                    return year

        return self._extract_year(content[:50000].decode("utf-8", errors="ignore"))

    def _resolve_pdf(self, url: str) -> tuple[requests.Response, bytes, str]:
        response = self.session.get(url, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
        response.raise_for_status()

        if self._is_pdf_response(response):
            return response, response.content, response.url

        ctype = response.headers.get("Content-Type", "").lower()
        if "text/html" not in ctype:
            raise ValueError(f"URL did not return PDF/HTML (Content-Type: {ctype or 'unknown'})")

        soup = BeautifulSoup(response.content, "html.parser")
        pdf_links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if ".pdf" in href.lower():
                pdf_links.append(requests.compat.urljoin(response.url, href))

        if not pdf_links:
            raise ValueError("No PDF links found on HTML page")

        pdf_response = self.session.get(pdf_links[0], timeout=DEFAULT_TIMEOUT, allow_redirects=True)
        pdf_response.raise_for_status()
        if not self._is_pdf_response(pdf_response):
            raise ValueError("Resolved file is not a PDF")

        return pdf_response, pdf_response.content, pdf_response.url

    def download(self, url: str) -> DownloadResult:
        normalized = url.strip()
        if not normalized:
            return DownloadResult(url=url, status="skipped", message="Empty URL")

        if normalized in self.url_manifest:
            return DownloadResult(
                url=normalized,
                status="skipped",
                message=f"Already downloaded: {self.url_manifest[normalized]}",
            )

        try:
            response, content, source_url = self._resolve_pdf(normalized)
            digest = self._sha256_bytes(content)

            if digest in self.hash_manifest:
                existing = self.hash_manifest[digest]
                self.url_manifest[normalized] = existing
                self._save_json(self.url_manifest_path, self.url_manifest)
                return DownloadResult(url=normalized, status="skipped", message=f"Duplicate file hash: {existing}")

            year = self._detect_year(source_url, response, content) or "unknown"
            target_dir = self.raw_pdfs / year
            target_dir.mkdir(parents=True, exist_ok=True)

            target = target_dir / self._filename_from_response(response, source_url)
            if target.exists() and self._sha256_bytes(target.read_bytes()) != digest:
                counter = 1
                while True:
                    candidate = target_dir / f"{target.stem}_{counter}{target.suffix}"
                    if not candidate.exists():
                        target = candidate
                        break
                    counter += 1

            target.write_bytes(content)
            rel_path = str(target.relative_to(self.root_dir))

            self.url_manifest[normalized] = rel_path
            self.hash_manifest[digest] = rel_path
            self._save_json(self.url_manifest_path, self.url_manifest)
            self._save_json(self.hash_manifest_path, self.hash_manifest)

            return DownloadResult(url=normalized, status="ok", message="Downloaded", saved_path=rel_path)
        except Exception as exc:  # noqa: BLE001
            result = DownloadResult(url=normalized, status="failed", message=str(exc))
            self._log_failure(result)
            return result


def load_urls(url_file: Path | None, cli_urls: list[str]) -> list[str]:
    urls: list[str] = []
    if url_file and url_file.exists():
        for line in url_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)

    urls.extend(cli_urls)

    seen: set[str] = set()
    deduped: list[str] = []
    for value in urls:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download NORCET PDFs into year-wise folders")
    parser.add_argument("urls", nargs="*", help="One or more direct/page URLs")
    parser.add_argument("--url-file", type=Path, help="Text file with one URL per line")
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root path (defaults to norcet-papers)",
    )
    parser.add_argument("--min-year", type=int, default=2012, help="Minimum expected exam year")
    parser.add_argument("--max-year", type=int, default=datetime.now().year, help="Maximum expected exam year")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    urls = load_urls(args.url_file, args.urls)
    if not urls:
        print("No URLs provided. Use --url-file or positional URLs.", file=sys.stderr)
        return 1

    downloader = NorcetDownloader(args.root_dir, min_year=args.min_year, max_year=args.max_year)
    print(f"Processing {len(urls)} URL(s)...")

    ok = skipped = failed = 0
    for url in urls:
        result = downloader.download(url)
        if result.status == "ok":
            ok += 1
            print(f"[OK] {url} -> {result.saved_path}")
        elif result.status == "skipped":
            skipped += 1
            print(f"[SKIP] {url} ({result.message})")
        else:
            failed += 1
            print(f"[FAIL] {url} ({result.message})")

    print(f"\nSummary: ok={ok}, skipped={skipped}, failed={failed}")
    if failed:
        print(f"See failures log: {downloader.failure_log_path}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
