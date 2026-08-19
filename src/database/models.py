"""Modelo de datos. SQLite hoy; el esquema es portable a PostgreSQL."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Signal(Base):
    """Una señal: un indicio observable en el presente con implicancias de futuro.

    La unidad de análisis es la señal, no el artículo.
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # --- Ficha obligatoria -------------------------------------------------
    title: Mapped[str] = mapped_column(String(400))
    link: Mapped[str] = mapped_column(String(1200))
    quote: Mapped[str | None] = mapped_column(Text)
    why_it_matters: Mapped[str | None] = mapped_column(Text)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    publication_date: Mapped[date | None] = mapped_column(Date)
    theme: Mapped[str | None] = mapped_column(String(200))
    thematic_relation: Mapped[str | None] = mapped_column(String(20))
    steep: Mapped[str | None] = mapped_column(String(20))
    relevance: Mapped[int | None] = mapped_column(Integer)
    utility: Mapped[str | None] = mapped_column(String(20))
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_domain: Mapped[str | None] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(20), default="scraper")
    status: Mapped[str] = mapped_column(String(20), default="unverified")

    # --- Procedencia y trazabilidad ---------------------------------------
    original_title: Mapped[str | None] = mapped_column(String(600))
    canonical_url: Mapped[str | None] = mapped_column(String(1200))
    url_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    text_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    source_owner: Mapped[str | None] = mapped_column(String(200))
    author: Mapped[str | None] = mapped_column(String(300))
    language: Mapped[str | None] = mapped_column(String(10))
    publication_date_confidence: Mapped[str | None] = mapped_column(String(10))
    publication_date_method: Mapped[str | None] = mapped_column(String(40))

    # --- Contenido ---------------------------------------------------------
    raw_text: Mapped[str | None] = mapped_column(Text)
    cleaned_text: Mapped[str | None] = mapped_column(Text)
    article_summary: Mapped[str | None] = mapped_column(Text)
    quote_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    quote_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Scraping ----------------------------------------------------------
    scraping_method: Mapped[str | None] = mapped_column(String(40))
    scraping_success: Mapped[bool] = mapped_column(Boolean, default=True)
    scraping_error: Mapped[str | None] = mapped_column(Text)

    # --- Propuestas de la IA (nunca sobrescriben el juicio humano) ---------
    ai_generated_title: Mapped[str | None] = mapped_column(String(400))
    ai_suggested_theme: Mapped[str | None] = mapped_column(String(200))
    ai_suggested_relation: Mapped[str | None] = mapped_column(String(20))
    ai_suggested_steep: Mapped[str | None] = mapped_column(String(20))
    ai_suggested_relevance: Mapped[int | None] = mapped_column(Integer)
    ai_suggested_utility: Mapped[str | None] = mapped_column(String(20))
    ai_why_it_matters: Mapped[str | None] = mapped_column(Text)
    ai_reasoning_short: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(String(120))
    ai_prompt_version: Mapped[str | None] = mapped_column(String(60))
    ai_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Semántica ---------------------------------------------------------
    embedding_json: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    embedding_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cluster_id: Mapped[int | None] = mapped_column(Integer, index=True)
    cluster_run_id: Mapped[int | None] = mapped_column(ForeignKey("cluster_runs.id"))
    semantic_duplicate_group: Mapped[int | None] = mapped_column(Integer, index=True)
    duplicate_score: Mapped[float | None] = mapped_column(Float)

    # --- Revisión humana ---------------------------------------------------
    manual_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        UniqueConstraint("url_hash", name="uq_signals_url_hash"),
        Index("ix_signals_theme_steep", "theme", "steep"),
        Index("ix_signals_status", "status"),
        Index("ix_signals_publication_date", "publication_date"),
    )

    # -- helpers ------------------------------------------------------------
    @property
    def embedding(self) -> list[float] | None:
        return json.loads(self.embedding_json) if self.embedding_json else None

    @embedding.setter
    def embedding(self, vector: list[float] | None) -> None:
        self.embedding_json = json.dumps(vector) if vector is not None else None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Signal {self.id}: {self.title[:60]!r}>"


class ClusterRun(Base):
    """Cada corrida de clustering guarda su configuración: reproducibilidad."""

    __tablename__ = "cluster_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    params_json: Mapped[str | None] = mapped_column(Text)
    n_signals: Mapped[int | None] = mapped_column(Integer)
    n_clusters: Mapped[int | None] = mapped_column(Integer)
    n_noise: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    clusters: Mapped[list["Cluster"]] = relationship(back_populates="run")


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("cluster_runs.id"))
    cluster_index: Mapped[int] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    size: Mapped[int | None] = mapped_column(Integer)
    label_model: Mapped[str | None] = mapped_column(String(120))
    label_prompt_version: Mapped[str | None] = mapped_column(String(60))

    run: Mapped[ClusterRun] = relationship(back_populates="clusters")

    __table_args__ = (UniqueConstraint("run_id", "cluster_index", name="uq_cluster_run_idx"),)


class ProcessingLog(Base):
    """Registro de operaciones: scraping, IA, embeddings, clustering, imports."""

    __tablename__ = "processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stage: Mapped[str] = mapped_column(String(40), index=True)
    level: Mapped[str] = mapped_column(String(10), default="info")
    url: Mapped[str | None] = mapped_column(String(1200))
    signal_id: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text)


class AuditRecord(Base):
    """Auditoría de 10 al azar exigida por la guía de la cátedra."""

    __tablename__ = "audit_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    batch_id: Mapped[str] = mapped_column(String(40), index=True)
    signal_id: Mapped[int] = mapped_column(Integer)
    link_ok: Mapped[bool | None] = mapped_column(Boolean)
    quote_ok: Mapped[bool | None] = mapped_column(Boolean)
    claim_ok: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)
    auditor: Mapped[str | None] = mapped_column(String(120))
