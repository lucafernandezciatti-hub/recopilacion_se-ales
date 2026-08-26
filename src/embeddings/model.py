"""Cálculo de embeddings de las señales.

El vector se calcula sobre `título + cita`: son los dos campos que describen la
señal en sí, ya curados y verificados. El artículo completo metería el ruido
editorial del medio (secciones, publicidad, notas relacionadas) dentro del
espacio semántico y arruinaría el clustering.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.config import settings
from src.database import repository as repo
from src.database.models import Signal

logger = logging.getLogger(__name__)

_model = None


def embedding_model_name() -> str:
    return settings()["embeddings"]["model"]


def get_model():
    """Carga diferida y única: bajar el modelo tarda y pesa cientos de MB."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(embedding_model_name())
    return _model


def signal_text(signal: Signal) -> str:
    parts = [signal.title or "", signal.quote or ""]
    return "\n".join(part.strip() for part in parts if part.strip())


def compute_missing_embeddings(session: Session, *, progress=None) -> int:
    """Calcula y persiste los embeddings faltantes. Devuelve cuántos generó."""
    pending = [s for s in repo.signals_without_embedding(session) if signal_text(s)]
    if not pending:
        return 0

    cfg = settings()["embeddings"]
    model = get_model()
    generated = 0
    batch_size = cfg["batch_size"]
    model_name = embedding_model_name()

    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        vectors = model.encode(
            [signal_text(s) for s in batch],
            batch_size=batch_size,
            normalize_embeddings=cfg["normalize"],
            show_progress_bar=False,
        )
        now = datetime.now(timezone.utc)
        for signal, vector in zip(batch, vectors):
            signal.embedding = [float(x) for x in vector]
            signal.embedding_model = model_name
            signal.embedding_generated_at = now
            generated += 1
        if progress is not None:
            progress(min(start + batch_size, len(pending)), len(pending))

    repo.log(session, "embeddings", f"{generated} embeddings generados con {model_name}")
    return generated
