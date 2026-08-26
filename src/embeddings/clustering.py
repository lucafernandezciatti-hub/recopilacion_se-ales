"""Clustering semántico: UMAP para reducir, HDBSCAN para agrupar.

HDBSCAN no fuerza a que toda señal entre en un cluster: lo que no tiene densidad
suficiente queda como ruido (`cluster_id = None`). Eso es deseable — un corpus de
horizon scanning tiene señales sueltas que no forman fenómeno.

Se usa `sklearn.cluster.HDBSCAN` en vez del paquete `hdbscan` standalone: es el
mismo algoritmo con los mismos parámetros, pero viaja en las wheels compiladas de
scikit-learn y no necesita toolchain de C++ en Windows.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from src.config import settings
from src.database import repository as repo
from src.database.models import Cluster, Signal

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ClusteringOutcome:
    run_id: int
    n_signals: int
    n_clusters: int
    n_noise: int


def _reduce(vectors: np.ndarray, cfg: dict, random_state: int) -> np.ndarray:
    """UMAP a baja dimensión antes de HDBSCAN.

    HDBSCAN degrada en espacios de cientos de dimensiones (maldición de la
    dimensionalidad): todas las distancias se parecen entre sí y no hay densidad
    distinguible. Reducir primero es la práctica estándar.
    """
    import umap

    n_components = min(cfg["n_components"], max(2, vectors.shape[0] - 2))
    reducer = umap.UMAP(
        n_neighbors=min(cfg["n_neighbors"], max(2, vectors.shape[0] - 1)),
        min_dist=cfg["min_dist"],
        n_components=n_components,
        metric=cfg["metric"],
        random_state=random_state,
    )
    return reducer.fit_transform(vectors)


def run_clustering(session: Session) -> ClusteringOutcome:
    from sklearn.cluster import HDBSCAN

    cfg = settings()["clustering"]
    random_state = cfg["random_state"]

    signals: list[Signal] = [
        s for s in repo.list_signals(session) if s.embedding_json
    ]
    if len(signals) < 3:
        raise ValueError(
            f"Hacen falta al menos 3 señales con embedding para clusterizar (hay {len(signals)}). "
            "Corré primero el cálculo de embeddings."
        )

    vectors = np.array([s.embedding for s in signals], dtype=np.float32)

    reduced = _reduce(vectors, cfg["umap_for_clustering"], random_state)

    hdb_cfg = cfg["hdbscan"]
    labels = HDBSCAN(
        min_cluster_size=hdb_cfg["min_cluster_size"],
        min_samples=hdb_cfg["min_samples"],
        metric=hdb_cfg["metric"],
        cluster_selection_method=hdb_cfg["cluster_selection_method"],
    ).fit_predict(reduced)

    cluster_indexes = sorted({int(label) for label in labels if label >= 0})
    n_noise = int((labels < 0).sum())

    run = repo.create_cluster_run(
        session,
        embedding_model=signals[0].embedding_model,
        params_json=json.dumps(
            {"umap": cfg["umap_for_clustering"], "hdbscan": hdb_cfg, "random_state": random_state},
            ensure_ascii=False,
        ),
        n_signals=len(signals),
        n_clusters=len(cluster_indexes),
        n_noise=n_noise,
    )

    sizes = {index: int((labels == index).sum()) for index in cluster_indexes}
    for index in cluster_indexes:
        session.add(
            Cluster(run_id=run.id, cluster_index=index, size=sizes[index])
        )

    for signal, label in zip(signals, labels):
        signal.cluster_id = int(label) if label >= 0 else None
        signal.cluster_run_id = run.id

    repo.log(
        session,
        "clustering",
        f"run {run.id}: {len(cluster_indexes)} clusters, {n_noise} señales sin cluster",
    )
    return ClusteringOutcome(run.id, len(signals), len(cluster_indexes), n_noise)
