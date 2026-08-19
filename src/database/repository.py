"""Acceso a datos. Toda consulta al corpus pasa por acá."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.models import AuditRecord, Cluster, ClusterRun, ProcessingLog, Signal


# --- señales ---------------------------------------------------------------
def get_signal(session: Session, signal_id: int) -> Signal | None:
    return session.get(Signal, signal_id)


def find_by_url_hash(session: Session, url_hash: str) -> Signal | None:
    return session.scalar(select(Signal).where(Signal.url_hash == url_hash))


def find_by_text_hash(session: Session, text_hash: str) -> Signal | None:
    if not text_hash:
        return None
    return session.scalar(select(Signal).where(Signal.text_hash == text_hash))


def list_signals(
    session: Session,
    *,
    status: str | None = None,
    include_demo: bool = True,
    limit: int | None = None,
) -> list[Signal]:
    stmt = select(Signal)
    if status:
        stmt = stmt.where(Signal.status == status)
    if not include_demo:
        stmt = stmt.where(Signal.is_demo.is_(False))
    stmt = stmt.order_by(Signal.id)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def count_signals(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Signal)) or 0


def add_signal(session: Session, signal: Signal) -> Signal:
    session.add(signal)
    session.flush()
    return signal


def signals_without_embedding(session: Session) -> list[Signal]:
    return list(session.scalars(select(Signal).where(Signal.embedding_json.is_(None))))


# --- logs ------------------------------------------------------------------
def log(
    session: Session,
    stage: str,
    message: str,
    *,
    level: str = "info",
    url: str | None = None,
    signal_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        ProcessingLog(
            stage=stage,
            level=level,
            message=message,
            url=url,
            signal_id=signal_id,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
        )
    )


def recent_logs(session: Session, stage: str | None = None, limit: int = 200) -> list[ProcessingLog]:
    stmt = select(ProcessingLog).order_by(ProcessingLog.id.desc()).limit(limit)
    if stage:
        stmt = select(ProcessingLog).where(ProcessingLog.stage == stage).order_by(
            ProcessingLog.id.desc()
        ).limit(limit)
    return list(session.scalars(stmt))


# --- clustering ------------------------------------------------------------
def create_cluster_run(session: Session, **kwargs) -> ClusterRun:
    session.execute(
        ClusterRun.__table__.update().values(is_active=False)
    )
    run = ClusterRun(**kwargs)
    session.add(run)
    session.flush()
    return run


def active_run(session: Session) -> ClusterRun | None:
    return session.scalar(
        select(ClusterRun).where(ClusterRun.is_active.is_(True)).order_by(ClusterRun.id.desc())
    )


def clusters_for_run(session: Session, run_id: int) -> list[Cluster]:
    return list(session.scalars(select(Cluster).where(Cluster.run_id == run_id)))


# --- auditoría -------------------------------------------------------------
def add_audit_record(session: Session, **kwargs) -> AuditRecord:
    record = AuditRecord(**kwargs)
    session.add(record)
    session.flush()
    return record


def audit_batches(session: Session) -> list[str]:
    return list(
        session.scalars(select(AuditRecord.batch_id).distinct().order_by(AuditRecord.batch_id))
    )


def touch_reviewed(signal: Signal, reviewer: str | None = None) -> None:
    signal.reviewed_at = datetime.now(timezone.utc)
    signal.reviewed_by = reviewer
