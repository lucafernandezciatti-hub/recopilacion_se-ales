"""Esquemas Pydantic. Nada entra a la DB sin validarse acá."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from src.signals.enums import DateConfidence, Origin, Status, Steep, ThematicRelation, Utility


class SignalAnalysis(BaseModel):
    """Salida estructurada del clasificador. La IA propone; el humano valida."""

    signal_title: str = Field(min_length=10, max_length=250)
    theme: str = Field(min_length=2, max_length=200)
    thematic_relation: ThematicRelation
    steep: Steep
    relevance: int = Field(ge=1, le=10)
    suggested_utility: Utility
    why_it_matters_suggestion: str = Field(min_length=20, max_length=600)
    short_reasoning: str = Field(min_length=10, max_length=600)
    quote: str = Field(min_length=40, max_length=800)

    @field_validator("signal_title")
    @classmethod
    def title_is_not_a_headline(cls, v: str) -> str:
        v = v.strip()
        if v.isupper():
            raise ValueError("el título de señal no debe ir en mayúsculas de titular")
        return v

    @field_validator("why_it_matters_suggestion", "short_reasoning")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class SignalCreate(BaseModel):
    """Ficha completa lista para persistir."""

    model_config = {"arbitrary_types_allowed": True}

    title: str
    link: str
    quote: str | None = None
    why_it_matters: str | None = None
    publication_date: date | None = None
    publication_date_confidence: DateConfidence | None = None
    theme: str | None = None
    thematic_relation: ThematicRelation | None = None
    steep: Steep | None = None
    relevance: int | None = Field(default=None, ge=1, le=10)
    utility: Utility | None = None
    source_name: str | None = None
    source_domain: str | None = None
    source_owner: str | None = None
    origin: Origin = Origin.SCRAPER
    status: Status = Status.UNVERIFIED
    original_title: str | None = None
    canonical_url: str | None = None
    language: str | None = None
    is_demo: bool = False
