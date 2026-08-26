#!/usr/bin/env python3
"""Carga señales clasificadas desde un JSON al corpus.

Valida cada ficha antes de persistirla. Las señales sin cita se rechazan.
Las citas recolectadas por lectura remota entran con quote_verified = False:
hay que correr scripts/verify_quotes.py para validarlas contra el original.

Uso:
    python scripts/load_signals.py data/signals_ronda1.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# En consolas Windows con codepage no-UTF-8 (cp1252), un título con un carácter
# especial (guiones largos, espacios finos, etc.) hace crashear el print y,
# como pasa dentro del `with get_session()`, revierte toda la carga. Forzamos
# UTF-8 con reemplazo en vez de fallar.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collection.normalize import domain_of, normalize_url, url_hash  # noqa: E402
from src.config import source_registry  # noqa: E402
from src.database import repository as repo  # noqa: E402
from src.database.models import Signal  # noqa: E402
from src.database.session import get_session, init_db  # noqa: E402
from src.signals.enums import Origin, Status  # noqa: E402
from src.signals.schemas import SignalAnalysis  # noqa: E402

MIN_QUOTE_CHARS = 40


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def resolve_source(domain: str, fallback: str | None) -> tuple[str, str]:
    entry = source_registry().get(domain)
    if entry:
        return entry.get("name", fallback or domain), entry.get("owner", fallback or domain)
    return fallback or domain, fallback or domain


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--origin", default=Origin.SCRAPER.value)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.path.read_text(encoding="utf-8"))
    entries = payload.get("signals", [])
    collected_via = payload.get("collected_via", "unknown")

    init_db()
    created = skipped = rejected = 0

    with get_session() as session:
        for entry in entries:
            url = entry.get("url", "")
            quote = (entry.get("quote") or "").strip()

            if len(quote) < MIN_QUOTE_CHARS:
                print(f"RECHAZADA (sin cita usable): {url}")
                repo.log(session, "import", "señal sin cita usable", level="error", url=url)
                rejected += 1
                continue

            try:
                normalized = normalize_url(url)
            except ValueError as exc:
                print(f"RECHAZADA (URL inválida): {url} :: {exc}")
                rejected += 1
                continue

            # Validación de vocabularios y rangos con el mismo esquema que usa la IA.
            try:
                SignalAnalysis(
                    signal_title=entry["title"],
                    theme=entry["theme"],
                    thematic_relation=entry["thematic_relation"],
                    steep=entry["steep"],
                    relevance=entry["relevance"],
                    suggested_utility=entry["ai_suggested_utility"],
                    why_it_matters_suggestion=entry["ai_why_it_matters"],
                    short_reasoning=entry["ai_reasoning_short"],
                    quote=quote,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"RECHAZADA (esquema inválido): {url} :: {exc}")
                rejected += 1
                continue

            hashed = url_hash(normalized)
            effective_hash = entry.get("url_hash") or hashed
            if repo.find_by_url_hash(session, effective_hash) or (
                effective_hash != hashed and repo.find_by_url_hash(session, hashed)
            ):
                print(f"DUPLICADA: {url}")
                skipped += 1
                continue

            domain = domain_of(normalized)
            source_name, source_owner = resolve_source(domain, entry.get("source_name"))

            publication_date = parse_date(entry.get("publication_date"))
            signal = Signal(
                title=entry["title"],
                link=normalized,
                canonical_url=entry.get("canonical_url") or normalized,
                url_hash=effective_hash,
                quote=quote,
                quote_verified=False,
                why_it_matters=None,          # decisión humana pendiente
                utility=None,                 # decisión humana pendiente
                publication_date=publication_date,
                publication_date_confidence=(
                    entry.get("publication_date_confidence")
                    or ("medium" if publication_date else None)
                ),
                publication_date_method=(
                    entry.get("publication_date_method")
                    or ("remote_read" if publication_date else None)
                ),
                theme=entry["theme"],
                thematic_relation=entry["thematic_relation"],
                steep=entry["steep"],
                relevance=entry["relevance"],
                source_name=source_name,
                source_domain=domain,
                source_owner=source_owner,
                original_title=entry.get("original_title"),
                origin=args.origin,
                status=Status.UNVERIFIED.value,
                language=entry.get("language") or "es",
                cleaned_text=entry.get("cleaned_text"),
                text_hash=entry.get("text_hash"),
                scraping_method=entry.get("scraping_method") or collected_via,
                scraping_success=True,
                ai_generated_title=entry["title"],
                ai_suggested_theme=entry["theme"],
                ai_suggested_relation=entry["thematic_relation"],
                ai_suggested_steep=entry["steep"],
                ai_suggested_relevance=entry["relevance"],
                ai_suggested_utility=entry["ai_suggested_utility"],
                ai_why_it_matters=entry["ai_why_it_matters"],
                ai_reasoning_short=entry["ai_reasoning_short"],
                ai_prompt_version="signal_classifier_v1",
                ai_analyzed_at=datetime.now(timezone.utc),
                manual_notes=entry.get("flag"),
                collected_at=datetime.now(timezone.utc),
            )

            if args.dry_run:
                print(f"OK (dry-run): {entry['title']}")
            else:
                repo.add_signal(session, signal)
                repo.log(session, "import", "señal importada", signal_id=signal.id, url=normalized)
                print(f"CREADA #{signal.id}: {entry['title']}")
            created += 1

        total = repo.count_signals(session)

    print(
        f"\ncreadas={created} duplicadas={skipped} rechazadas={rejected} "
        f"| total en corpus={total}"
    )
    print("Recordatorio: todas las citas quedan SIN VERIFICAR. Corré scripts/verify_quotes.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
