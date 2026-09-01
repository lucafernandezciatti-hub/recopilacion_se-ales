#!/usr/bin/env python3
"""Exporta la clusterización a un JSON versionable, para que la use todo el equipo.

El clustering es *global*: HDBSCAN agrupa por densidad sobre el corpus entero, así
que no basta con que cada persona corra `cluster_signals.py`. Si su corpus difiere
en una señal, si cargó las rondas en otro orden —el orden de las filas cambia la
proyección de UMAP— o si tiene otra versión de umap/sklearn, obtiene una partición
distinta, no "la misma con ruido". Por eso los clusters se calculan UNA vez y se
versionan, igual que las revisiones.

La señal se identifica por `url_hash`, no por `id`: el id es el orden de inserción
en cada base local y no significa lo mismo en dos máquinas.

    python scripts/export_clusters.py --autor luca
    python scripts/export_clusters.py --autor luca --run 2
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_DIR  # noqa: E402
from src.database import repository as repo  # noqa: E402
from src.database.models import ClusterRun  # noqa: E402
from src.database.session import get_session, init_db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--autor", required=True, help="quién define la clusterización del grupo")
    parser.add_argument("--run", type=int, default=None, help="id de corrida (default: la activa)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    out_path = args.out or Path(DATA_DIR) / "clusters.json"

    init_db()
    with get_session() as session:
        if args.run is not None:
            run = session.get(ClusterRun, args.run)
            if run is None:
                print(f"No existe la corrida #{args.run}.")
                return 1
        else:
            run = repo.active_run(session)
            if run is None:
                print("No hay ninguna corrida de clustering. Corré antes scripts/cluster_signals.py")
                return 1

        clusters = [
            {
                "index": c.cluster_index,
                "size": c.size,
                "label": c.label,
                "description": c.description,
                "label_model": c.label_model,
                "label_prompt_version": c.label_prompt_version,
            }
            for c in sorted(repo.clusters_for_run(session, run.id), key=lambda c: c.cluster_index)
        ]

        # Se exportan TAMBIÉN las señales sin cluster (`cluster: null`). Son parte
        # del resultado: HDBSCAN las dejó como ruido y el import tiene que poder
        # reproducir eso, no dejarlas con una asignación vieja.
        asignaciones = []
        sin_hash = 0
        for signal in repo.list_signals(session):
            if signal.cluster_run_id != run.id:
                continue
            if not signal.url_hash:
                sin_hash += 1
                continue
            asignaciones.append(
                {
                    "url_hash": signal.url_hash,
                    "cluster": signal.cluster_id,
                    "link": signal.link,          # para auditar a mano
                    "title": (signal.title or "")[:120],
                }
            )

        payload = {
            "_comentario": (
                "Clusterización de referencia del grupo. Se aplica con "
                "scripts/import_clusters.py. Las señales se identifican por url_hash "
                "porque el id depende del orden de carga de cada base local. "
                "OJO: correr cluster_signals.py después de importar pisa esto."
            ),
            "autor": args.autor.strip(),
            "exportado_en": datetime.now(timezone.utc).isoformat(),
            "embedding_model": run.embedding_model,
            "params": json.loads(run.params_json) if run.params_json else None,
            "n_signals": run.n_signals,
            "n_clusters": run.n_clusters,
            "n_noise": run.n_noise,
            "clusters": clusters,
            "asignaciones": asignaciones,
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    con_cluster = sum(1 for a in asignaciones if a["cluster"] is not None)
    try:
        shown = out_path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        shown = out_path.as_posix()
    print(
        f"corrida #{run.id}: {len(clusters)} clusters, {con_cluster} señales asignadas, "
        f"{len(asignaciones) - con_cluster} sin cluster -> {shown}"
    )
    if sin_hash:
        print(f"AVISO: {sin_hash} señales sin url_hash quedaron afuera (no se pueden identificar).")
    print(f'Ahora: git add {shown} && git commit -m "clusters de referencia" && git push')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
