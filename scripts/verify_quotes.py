#!/usr/bin/env python3
"""Verifica que cada cita esté LITERALMENTE en el artículo original.

Este script necesita salida a internet: correlo en una máquina con red abierta.
Vuelve a descargar cada URL, extrae el texto y busca la cita carácter por carácter
(admitiendo sólo diferencias de espaciado, comillas tipográficas y guiones).

    python scripts/verify_quotes.py                 # todas las no verificadas
    python scripts/verify_quotes.py --all           # también las ya verificadas
    python scripts/verify_quotes.py --ids 3 7 12

Una cita que no se encuentra NO se borra: se marca y se reporta, para revisar el
método y no sólo el dato (guía Clase 3, "si falla una, se revisa el método").
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collection.extractor import extract  # noqa: E402
from src.config import settings  # noqa: E402
from src.database import repository as repo  # noqa: E402
from src.database.models import Signal  # noqa: E402
from src.database.session import get_session, init_db  # noqa: E402
from src.signals.validation import validate_quote  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="reverificar también las verificadas")
    parser.add_argument("--ids", type=int, nargs="*", help="verificar sólo estos ids")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    init_db()
    delay = settings()["scraping"]["delay_between_requests_seconds"]
    ok = failed = unreachable = 0
    report: list[tuple[int, str, str]] = []

    with get_session() as session, httpx.Client(follow_redirects=True, timeout=30) as client:
        signals = repo.list_signals(session)
        if args.ids:
            signals = [s for s in signals if s.id in set(args.ids)]
        elif not args.all:
            signals = [s for s in signals if not s.quote_verified]
        if args.limit:
            signals = signals[: args.limit]

        print(f"Verificando {len(signals)} señales...\n")

        for signal in signals:
            if not signal.quote:
                report.append((signal.id, "SIN_CITA", signal.link))
                failed += 1
                continue

            extraction = extract(signal.link, client=client)
            if not extraction.success:
                signal.scraping_error = extraction.error
                report.append((signal.id, "INACCESIBLE", f"{signal.link} :: {extraction.error}"))
                repo.log(
                    session, "verify", extraction.error or "inaccesible",
                    level="warning", signal_id=signal.id, url=signal.link,
                )
                unreachable += 1
                print(f"[{signal.id}] INACCESIBLE  {extraction.error}")
                time.sleep(delay)
                continue

            # Refrescamos el texto y la fecha con la extracción real.
            signal.cleaned_text = extraction.cleaned_text
            signal.text_hash = extraction.text_hash
            signal.scraping_method = extraction.method
            if extraction.publication_date and (
                signal.publication_date is None
                or signal.publication_date_confidence in (None, "low", "medium")
            ):
                signal.publication_date = extraction.publication_date
                signal.publication_date_confidence = extraction.publication_date_confidence
                signal.publication_date_method = extraction.publication_date_method

            if validate_quote(extraction.cleaned_text or "", signal.quote):
                signal.quote_verified = True
                signal.quote_verified_at = datetime.now(timezone.utc)
                ok += 1
                print(f"[{signal.id}] OK           {signal.title[:60]}")
            else:
                signal.quote_verified = False
                note = "cita no encontrada literalmente en el original"
                signal.manual_notes = f"{signal.manual_notes or ''}\n{note}".strip()
                report.append((signal.id, "CITA_NO_LITERAL", signal.link))
                repo.log(
                    session, "verify", note, level="error",
                    signal_id=signal.id, url=signal.link,
                )
                failed += 1
                print(f"[{signal.id}] CITA FALLA   {signal.title[:60]}")

            time.sleep(delay)

    print(f"\nverificadas={ok}  citas_fallidas={failed}  inaccesibles={unreachable}")
    if report:
        print("\nRevisar:")
        for signal_id, kind, detail in report:
            print(f"  #{signal_id:<4} {kind:<16} {detail}")
    if failed:
        print(
            "\nATENCIÓN: una cita fallida no se parchea a mano. Revisá qué parte del "
            "pipeline la produjo antes de seguir cargando señales."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
