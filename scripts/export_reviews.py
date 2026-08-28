#!/usr/bin/env python3
"""Exporta las decisiones humanas del corpus a un JSON versionable.

La base local (`data/senales.db`) no se versiona, así que las revisiones no
viajan por git. Este script saca sólo lo que decidió una persona —utilidad, por
qué importa, estado, notas— y lo deja en `data/reviews_<autor>.json` para
commitear. El resto del corpus (citas, clasificación de la IA) ya está
versionado en `data/signals_ronda*.json` y no se duplica acá.

Un archivo por persona: así git nunca tiene que resolver un conflicto.

    python scripts/export_reviews.py --autor luca
    python scripts/export_reviews.py --autor luca --solo-mias
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_DIR  # noqa: E402
from src.database import repository as repo  # noqa: E402
from src.database.session import get_session, init_db  # noqa: E402
from src.signals.enums import Status  # noqa: E402

# Campos que decide una persona. Todo lo demás lo produce el pipeline y ya viaja
# por git, así que exportarlo sería duplicar la fuente de verdad.
HUMAN_FIELDS = ("utility", "why_it_matters", "status", "manual_notes")


def has_human_input(signal) -> bool:
    """Sólo lo que decidió una persona.

    `manual_notes` NO alcanza como señal de revisión humana: verify_quotes.py
    escribe ahí automáticamente las citas que fallan. Si lo contáramos, el
    export se llenaría de señales que nadie miró y el import reportaría
    desacuerdos inventados entre compañeras.
    """
    return bool(
        signal.utility
        or signal.why_it_matters
        or signal.status != Status.UNVERIFIED.value
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--autor", required=True, help="tu nombre, en minúsculas y sin espacios")
    parser.add_argument(
        "--solo-mias",
        action="store_true",
        help="exportar sólo las señales cuyo 'revisado por' coincide con --autor",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    slug = re.sub(r"[^a-z0-9_-]", "", args.autor.strip().lower().replace(" ", "-"))
    if not slug:
        print("El nombre de autor no puede quedar vacío después de normalizarlo.")
        return 1

    out_path = args.out or Path(DATA_DIR) / f"reviews_{slug}.json"

    init_db()
    entries = []
    with get_session() as session:
        for signal in repo.list_signals(session):
            if not has_human_input(signal):
                continue
            if args.solo_mias and (signal.reviewed_by or "").strip().lower() != args.autor.strip().lower():
                continue
            entries.append(
                {
                    "id": signal.id,
                    "link": signal.link,  # para poder auditar a mano contra qué señal es
                    **{field: getattr(signal, field) for field in HUMAN_FIELDS},
                    "reviewed_by": signal.reviewed_by,
                    "reviewed_at": signal.reviewed_at.isoformat() if signal.reviewed_at else None,
                }
            )

    payload = {
        "autor": args.autor.strip(),
        "_comentario": (
            "Decisiones humanas sobre el corpus. Se aplica con "
            "scripts/import_reviews.py. Un archivo por persona."
        ),
        "reviews": entries,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    con_utilidad = sum(1 for e in entries if e["utility"])
    try:
        shown = out_path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        shown = out_path.as_posix()
    print(f"{len(entries)} señales revisadas exportadas ({con_utilidad} con utilidad) -> {shown}")
    print(f'Ahora: git add {shown} && git commit -m "revisiones {args.autor}" && git push')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
