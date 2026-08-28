#!/usr/bin/env python3
"""Aplica a la base local las revisiones exportadas por todo el equipo.

Lee todos los `data/reviews_*.json` y escribe las decisiones humanas sobre el
corpus local. Pensado para correr después de cada `git pull`.

Si dos personas revisaron la misma señal con distinto criterio, NO se resuelve
en silencio: se reporta el desacuerdo y esa señal se deja como está, para que lo
decida el grupo. Un desacuerdo sobre la utilidad de una señal es justamente el
tipo de discusión que la Clase 4 pide tener, no un dato a pisar.

    python scripts/import_reviews.py
    python scripts/import_reviews.py --dry-run
    python scripts/import_reviews.py --forzar luca   # ante desacuerdo, gana ese autor
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_DIR  # noqa: E402
from src.database import repository as repo  # noqa: E402
from src.database.session import get_session, init_db  # noqa: E402

HUMAN_FIELDS = ("utility", "why_it_matters", "status", "manual_notes")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--forzar",
        metavar="AUTOR",
        help="ante un desacuerdo, aplicar la versión de este autor en vez de saltearla",
    )
    args = parser.parse_args()

    files = sorted(Path(DATA_DIR).glob("reviews_*.json"))
    if not files:
        print("No hay archivos data/reviews_*.json. ¿Hiciste git pull?")
        return 0

    # id -> lista de (autor, entrada); permite detectar desacuerdos entre personas.
    by_signal: dict[int, list[tuple[str, dict]]] = {}
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"SALTEADO {path.name}: no se pudo leer ({exc})")
            continue
        author = payload.get("autor") or path.stem.replace("reviews_", "")
        for entry in payload.get("reviews", []):
            by_signal.setdefault(int(entry["id"]), []).append((author, entry))
        print(f"leído {path.name}: {len(payload.get('reviews', []))} revisiones de {author}")

    applied = skipped = conflicts = 0
    conflict_report: list[str] = []

    init_db()
    with get_session() as session:
        for signal_id, candidates in sorted(by_signal.items()):
            signal = repo.get_signal(session, signal_id)
            if signal is None:
                print(f"SALTEADA #{signal_id}: no está en el corpus local")
                skipped += 1
                continue

            chosen_author, chosen = candidates[0]
            if len(candidates) > 1:
                # Sólo es desacuerdo si el juicio difiere; si coinciden, da igual quién.
                distinct = {
                    tuple(str(entry.get(field)) for field in HUMAN_FIELDS)
                    for _, entry in candidates
                }
                if len(distinct) > 1:
                    forced = [c for c in candidates if c[0].lower() == (args.forzar or "").lower()]
                    if forced:
                        chosen_author, chosen = forced[0]
                    else:
                        conflicts += 1
                        autores = ", ".join(
                            f"{a}={entry.get('utility') or '—'}" for a, entry in candidates
                        )
                        conflict_report.append(
                            f"  #{signal_id:<4} {signal.title[:58]}\n"
                            f"        {autores}"
                        )
                        continue

            for field in HUMAN_FIELDS:
                if chosen.get(field) is not None:
                    setattr(signal, field, chosen[field])
            signal.reviewed_by = chosen.get("reviewed_by") or chosen_author
            signal.reviewed_at = parse_dt(chosen.get("reviewed_at")) or signal.reviewed_at
            applied += 1

        if args.dry_run:
            session.rollback()

    print(
        f"\naplicadas={applied} salteadas={skipped} desacuerdos={conflicts}"
        + (" (dry-run: no se guardó nada)" if args.dry_run else "")
    )
    if conflict_report:
        print("\nDESACUERDOS — el grupo tiene que decidir (nadie pisó a nadie):")
        print("\n".join(conflict_report))
        print(
            "\nResolver hablándolo y volviendo a exportar, o correr de nuevo con "
            "--forzar <autor> si ya acordaron quién define."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
