#!/usr/bin/env python3
"""Aplica a la base local la clusterización de referencia del grupo.

Lee `data/clusters.json` y escribe las asignaciones tal cual las calculó quien
exportó. Correr después de cada `git pull`. Reemplaza a `cluster_signals.py`
para el uso diario: clusterizar de nuevo en cada máquina da particiones distintas
—el corpus, el orden de carga y las versiones de umap/sklearn cambian el
resultado—, así que se calcula una vez y todas importan lo mismo.

Las señales se emparejan por `url_hash`, que sale de la URL normalizada y vale lo
mismo en cualquier máquina; el `id` no, porque es el orden de inserción local.

    python scripts/import_clusters.py --dry-run    # ver qué haría, sin tocar nada
    python scripts/import_clusters.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_DIR  # noqa: E402
from src.database import repository as repo  # noqa: E402
from src.database.models import Cluster  # noqa: E402
from src.database.session import get_session, init_db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--archivo", type=Path, default=None)
    args = parser.parse_args()

    path = args.archivo or Path(DATA_DIR) / "clusters.json"
    if not path.exists():
        print(f"No existe {path}. ¿Hiciste git pull?")
        return 1
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"No se pudo leer {path}: {exc}")
        return 1

    asignaciones = {
        entry["url_hash"]: entry.get("cluster")
        for entry in payload.get("asignaciones", [])
        if entry.get("url_hash")
    }
    if not asignaciones:
        print("El archivo no trae asignaciones.")
        return 1

    autor = payload.get("autor", "?")
    print(
        f"{path.name}: clusterización de {autor}, "
        f"{payload.get('n_clusters')} clusters sobre {payload.get('n_signals')} señales"
    )

    init_db()
    with get_session() as session:
        senales = repo.list_signals(session)

        modelo_local = {s.embedding_model for s in senales if s.embedding_model}
        modelo_archivo = payload.get("embedding_model")
        if modelo_archivo and modelo_local and modelo_archivo not in modelo_local:
            print(
                f"AVISO: tus embeddings son de {sorted(modelo_local)} y el archivo se "
                f"calculó con {modelo_archivo}. Las asignaciones se aplican igual, pero "
                "el gráfico de clusters puede no cuadrar."
            )

        run = repo.create_cluster_run(
            session,
            embedding_model=modelo_archivo,
            params_json=json.dumps(
                {"importado_de": path.name, "autor": autor, "params": payload.get("params")},
                ensure_ascii=False,
            ),
            n_signals=payload.get("n_signals"),
            n_clusters=payload.get("n_clusters"),
            n_noise=payload.get("n_noise"),
        )

        aplicadas = ruido = fuera_del_archivo = 0
        vistos: set[str] = set()
        tamanos: dict[int, int] = {}

        for signal in senales:
            asignado = asignaciones.get(signal.url_hash or "", "__ausente__")
            if asignado == "__ausente__":
                # Señal que quien exportó no tenía: no forma parte de la partición
                # compartida. Se deja sin cluster antes que inventarle uno.
                signal.cluster_id = None
                signal.cluster_run_id = run.id
                fuera_del_archivo += 1
                continue
            vistos.add(signal.url_hash or "")
            signal.cluster_id = int(asignado) if asignado is not None else None
            signal.cluster_run_id = run.id
            if asignado is None:
                ruido += 1
            else:
                aplicadas += 1
                tamanos[int(asignado)] = tamanos.get(int(asignado), 0) + 1

        for cluster in payload.get("clusters", []):
            index = int(cluster["index"])
            session.add(
                Cluster(
                    run_id=run.id,
                    cluster_index=index,
                    # Tamaño real acá, no el del archivo: si a alguien le faltan
                    # señales, mejor que el número lo muestre a que mienta.
                    size=tamanos.get(index, 0),
                    label=cluster.get("label"),
                    description=cluster.get("description"),
                    label_model=cluster.get("label_model"),
                    label_prompt_version=cluster.get("label_prompt_version"),
                )
            )

        faltantes = len(asignaciones) - len(vistos)
        repo.log(
            session,
            "clustering",
            f"import de {path.name} ({autor}): run {run.id}, {aplicadas} señales asignadas",
        )

        if args.dry_run:
            session.rollback()

    print(
        f"\nasignadas={aplicadas} sin-cluster={ruido} "
        f"fuera-del-archivo={fuera_del_archivo} faltan-en-tu-corpus={faltantes}"
        + (" (dry-run: no se guardó nada)" if args.dry_run else "")
    )
    if faltantes or fuera_del_archivo:
        print(
            "\nTu corpus no coincide con el de quien exportó. Los clusters se aplicaron "
            "igual donde se pudo, pero conviene emparejar los corpus: revisá que estén "
            "cargadas todas las rondas de data/signals_ronda*.json."
        )
    if not args.dry_run:
        print("\nNO corras scripts/cluster_signals.py después de esto: recalcula y pisa el import.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
