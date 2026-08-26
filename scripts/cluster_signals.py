#!/usr/bin/env python3
"""Calcula embeddings y clusteriza el corpus.

La primera corrida descarga el modelo de embeddings (unos cientos de MB) y puede
tardar varios minutos; las siguientes reutilizan el modelo en caché y sólo
calculan los embeddings de las señales nuevas.

    python scripts/cluster_signals.py                 # embeddings faltantes + clustering
    python scripts/cluster_signals.py --solo-embeddings
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.session import get_session, init_db  # noqa: E402
from src.embeddings.clustering import run_clustering  # noqa: E402
from src.embeddings.model import compute_missing_embeddings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo-embeddings", action="store_true")
    args = parser.parse_args()

    init_db()
    with get_session() as session:
        def progress(done: int, total: int) -> None:
            print(f"  embeddings {done}/{total}", flush=True)

        generated = compute_missing_embeddings(session, progress=progress)
        print(f"embeddings nuevos: {generated}")

        if args.solo_embeddings:
            return 0

        outcome = run_clustering(session)
        print(
            f"\nrun #{outcome.run_id}: {outcome.n_clusters} clusters sobre "
            f"{outcome.n_signals} señales ({outcome.n_noise} sin cluster)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
