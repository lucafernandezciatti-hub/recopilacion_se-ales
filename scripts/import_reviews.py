#!/usr/bin/env python3
"""Aplica a la base local las revisiones exportadas por todo el equipo.

Lee todos los `data/reviews_*.json` y escribe las decisiones humanas sobre el
corpus local. Pensado para correr después de cada `git pull`.

Las señales se emparejan por `url_hash`, que sale de la URL normalizada y vale lo
mismo en cualquier máquina. Por `id` no: el id es el orden de inserción de cada
base local, así que si alguien cargó las rondas en otro orden su señal 42 no es la
misma que la tuya y la revisión terminaría aplicada a otra señal, sin error visible.

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

    # clave de señal -> lista de (autor, entrada); permite detectar desacuerdos.
    # La clave es ("hash", url_hash). ("id", n) es sólo para exports viejos: se
    # emparejan a ciegas, así que se avisa.
    by_signal: dict[tuple[str, str], list[tuple[str, dict]]] = {}
    legacy = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"SALTEADO {path.name}: no se pudo leer ({exc})")
            continue
        author = payload.get("autor") or path.stem.replace("reviews_", "")
        for entry in payload.get("reviews", []):
            url_hash = (entry.get("url_hash") or "").strip()
            if url_hash:
                key = ("hash", url_hash)
            elif entry.get("id") is not None:
                key = ("id", str(int(entry["id"])))
                legacy += 1
            else:
                continue
            by_signal.setdefault(key, []).append((author, entry))
        print(f"leído {path.name}: {len(payload.get('reviews', []))} revisiones de {author}")

    if legacy:
        print(
            f"AVISO: {legacy} revisiones vienen sin url_hash (export viejo) y se "
            "emparejan por id. El id depende del orden de carga de cada base: si no "
            "coincide, la revisión cae en otra señal. Pedí que vuelvan a exportar."
        )

    applied = skipped = conflicts = 0
    conflict_report: list[str] = []

    init_db()
    with get_session() as session:
        for (kind, value), candidates in sorted(by_signal.items()):
            if kind == "hash":
                signal = repo.find_by_url_hash(session, value)
            else:
                signal = repo.get_signal(session, int(value))
            if signal is None:
                referencia = candidates[0][1].get("link") or value
                print(f"SALTEADA {referencia[:70]}: no está en el corpus local")
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
                            f"  #{signal.id:<4} {(signal.title or '')[:58]}\n"
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
