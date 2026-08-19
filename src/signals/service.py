"""Pipeline de una señal: URL → normalización → dedupe → extracción → IA → persistencia."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.ai.provider import AIProvider, AnalysisResult
from src.collection.extractor import ExtractionResult, extract
from src.collection.normalize import normalize_url, url_hash
from src.database import repository as repo
from src.database.models import Signal
from src.signals.enums import Origin, Status
from src.signals.validation import quote_length_ok, validate_quote

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestOutcome:
    url: str
    status: str  # created | duplicate | failed | rejected
    signal_id: int | None = None
    reason: str | None = None


def _exists(session: Session, extraction: ExtractionResult) -> Signal | None:
    existing = repo.find_by_url_hash(session, extraction.url_hash or "")
    if existing:
        return existing
    if extraction.text_hash:
        return repo.find_by_text_hash(session, extraction.text_hash)
    return None


def signal_from_extraction(extraction: ExtractionResult, origin: Origin) -> Signal:
    return Signal(
        title=extraction.original_title or extraction.url,
        link=extraction.canonical_url or extraction.url,
        canonical_url=extraction.canonical_url,
        url_hash=extraction.url_hash,
        text_hash=extraction.text_hash,
        original_title=extraction.original_title,
        author=extraction.author,
        language=extraction.language,
        source_name=extraction.source_name,
        source_domain=extraction.domain,
        source_owner=extraction.source_owner,
        publication_date=extraction.publication_date,
        publication_date_confidence=extraction.publication_date_confidence,
        publication_date_method=extraction.publication_date_method,
        cleaned_text=extraction.cleaned_text,
        scraping_method=extraction.method,
        scraping_success=extraction.success,
        scraping_error=extraction.error,
        origin=origin.value,
        status=Status.UNVERIFIED.value,
        collected_at=datetime.now(timezone.utc),
    )


def apply_analysis(signal: Signal, result: AnalysisResult) -> bool:
    """Escribe las propuestas de la IA. Devuelve False si la salida fue rechazada.

    La IA nunca escribe `utility` ni `why_it_matters`: esos son juicio humano.
    """
    if result.analysis is None:
        return False

    analysis = result.analysis
    if not result.quote_valid:
        return False
    if not validate_quote(signal.cleaned_text or "", analysis.quote):
        return False

    signal.quote = analysis.quote.strip()
    signal.quote_verified = True
    signal.quote_verified_at = datetime.now(timezone.utc)

    signal.ai_generated_title = analysis.signal_title
    signal.ai_suggested_theme = analysis.theme
    signal.ai_suggested_relation = analysis.thematic_relation.value
    signal.ai_suggested_steep = analysis.steep.value
    signal.ai_suggested_relevance = analysis.relevance
    signal.ai_suggested_utility = analysis.suggested_utility.value
    signal.ai_why_it_matters = analysis.why_it_matters_suggestion
    signal.ai_reasoning_short = analysis.short_reasoning
    signal.ai_model = result.model
    signal.ai_prompt_version = result.prompt_version
    signal.ai_analyzed_at = datetime.now(timezone.utc)

    # Valores de trabajo: editables por el equipo en la pantalla de revisión.
    signal.title = analysis.signal_title
    signal.theme = analysis.theme
    signal.thematic_relation = analysis.thematic_relation.value
    signal.steep = analysis.steep.value
    signal.relevance = analysis.relevance
    return True


def ingest_url(
    session: Session,
    url: str,
    provider: AIProvider,
    *,
    origin: Origin = Origin.SCRAPER,
    client: httpx.Client | None = None,
) -> IngestOutcome:
    try:
        normalized = normalize_url(url)
    except ValueError as exc:
        repo.log(session, "scraping", f"URL inválida: {exc}", level="error", url=url)
        return IngestOutcome(url, "failed", reason=str(exc))

    existing = repo.find_by_url_hash(session, url_hash(normalized))
    if existing:
        return IngestOutcome(normalized, "duplicate", existing.id, "URL ya en el corpus")

    extraction = extract(normalized, client=client)
    if not extraction.success:
        repo.log(
            session, "scraping", extraction.error or "extracción fallida",
            level="error", url=normalized,
        )
        return IngestOutcome(normalized, "failed", reason=extraction.error)

    duplicate = _exists(session, extraction)
    if duplicate:
        return IngestOutcome(normalized, "duplicate", duplicate.id, "contenido ya en el corpus")

    signal = signal_from_extraction(extraction, origin)
    result = provider.analyze_signal(
        {
            "url": normalized,
            "source_name": extraction.source_name,
            "source_domain": extraction.domain,
            "publication_date": extraction.publication_date,
            "original_title": extraction.original_title,
            "cleaned_text": extraction.cleaned_text,
        }
    )

    if not apply_analysis(signal, result):
        repo.log(
            session, "ai", result.error or "análisis rechazado", level="error", url=normalized
        )
        return IngestOutcome(normalized, "rejected", reason=result.error or "análisis rechazado")

    if not quote_length_ok(signal.quote or ""):
        repo.log(session, "ai", "cita fuera de rango de longitud", level="warning", url=normalized)

    repo.add_signal(session, signal)
    repo.log(session, "scraping", "señal creada", signal_id=signal.id, url=normalized)
    return IngestOutcome(normalized, "created", signal.id)


def ingest_many(
    session: Session, urls: list[str], provider: AIProvider, **kwargs
) -> list[IngestOutcome]:
    """Una URL que falla nunca rompe el batch."""
    outcomes: list[IngestOutcome] = []
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        for url in urls:
            try:
                outcomes.append(ingest_url(session, url, provider, client=client, **kwargs))
            except Exception as exc:  # noqa: BLE001
                logger.exception("fallo inesperado ingiriendo %s", url)
                repo.log(session, "scraping", f"excepción: {exc}", level="error", url=url)
                outcomes.append(IngestOutcome(url, "failed", reason=str(exc)))
    return outcomes


def summarize(outcomes: list[IngestOutcome]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for outcome in outcomes:
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
    return {"total": len(outcomes), **counts}
