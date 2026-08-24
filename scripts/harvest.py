#!/usr/bin/env python3
"""Extrae contenido de una lista de URLs y deja candidatos listos para clasificar.

Uso:
    python scripts/harvest.py --urls urls.txt --out data/candidates.json
    python scripts/harvest.py --rss --out data/candidates.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collection.extractor import extract  # noqa: E402
from src.collection.normalize import normalize_url  # noqa: E402
from src.config import settings  # noqa: E402
from src.database.session import get_session, init_db  # noqa: E402
from src.database import repository as repo  # noqa: E402


def load_urls(path: Path) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", type=Path, help="archivo con una URL por línea")
    parser.add_argument("--rss", action="store_true", help="tomar URLs de los feeds configurados")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--out", type=Path, default=Path("data/candidates.json"))
    args = parser.parse_args()

    urls: list[str] = []
    if args.urls:
        urls.extend(load_urls(args.urls))
    if args.rss:
        from src.collection.rss import harvest_all

        urls.extend(item.url for item in harvest_all())

    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        try:
            normalized = normalize_url(url)
        except ValueError:
            continue
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    unique = unique[: args.limit]

    init_db()
    delay = settings()["scraping"]["delay_between_requests_seconds"]
    results: list[dict] = []
    failures: list[dict] = []

    with httpx.Client(follow_redirects=True, timeout=30) as client, get_session() as session:
        for i, url in enumerate(unique, 1):
            extraction = extract(url, client=client)
            if extraction.success:
                results.append(
                    {
                        "url": extraction.url,
                        "canonical_url": extraction.canonical_url,
                        "url_hash": extraction.url_hash,
                        "domain": extraction.domain,
                        "source_name": extraction.source_name,
                        "source_owner": extraction.source_owner,
                        "original_title": extraction.original_title,
                        "author": extraction.author,
                        "language": extraction.language,
                        "publication_date": (
                            extraction.publication_date.isoformat()
                            if extraction.publication_date else None
                        ),
                        "publication_date_confidence": extraction.publication_date_confidence,
                        "publication_date_method": extraction.publication_date_method,
                        "method": extraction.method,
                        "text_hash": extraction.text_hash,
                        "cleaned_text": extraction.cleaned_text,
                    }
                )
                print(f"[{i}/{len(unique)}] OK   {url}", flush=True)
            else:
                failures.append({"url": url, "error": extraction.error})
                repo.log(session, "scraping", extraction.error or "fallo", level="error", url=url)
                print(f"[{i}/{len(unique)}] FAIL {url} :: {extraction.error}", flush=True)
            time.sleep(delay)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"candidates": results, "failures": failures}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n{len(results)} extraidos, {len(failures)} fallidos -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
