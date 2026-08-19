"""Vocabularios controlados de la ficha de señal (guía Clase 3, UTDT DI)."""

from __future__ import annotations

from enum import StrEnum


class Steep(StrEnum):
    SOCIAL = "Social"
    TECHNOLOGICAL = "Technological"
    ECONOMIC = "Economic"
    ENVIRONMENTAL = "Environmental"
    POLITICAL = "Political"


class ThematicRelation(StrEnum):
    CORE = "core"
    ADJACENT = "adjacent"


class Utility(StrEnum):
    VERY_USEFUL = "very_useful"
    USEFUL = "useful"
    POOR = "poor"
    NOT_USEFUL = "not_useful"


class Origin(StrEnum):
    SCRAPER = "scraper"
    MANUAL = "manual"
    AI_SUGGESTED = "ai_suggested"


class Status(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class DateConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Etiquetas de interfaz en español. La DB guarda siempre el valor canónico.
STEEP_ES = {
    Steep.SOCIAL: "Social",
    Steep.TECHNOLOGICAL: "Tecnológico",
    Steep.ECONOMIC: "Económico",
    Steep.ENVIRONMENTAL: "Ambiental",
    Steep.POLITICAL: "Político",
}

RELATION_ES = {
    ThematicRelation.CORE: "Núcleo",
    ThematicRelation.ADJACENT: "Adyacente",
}

UTILITY_ES = {
    Utility.VERY_USEFUL: "Muy útil",
    Utility.USEFUL: "Útil",
    Utility.POOR: "Pobre",
    Utility.NOT_USEFUL: "No es útil",
}

ORIGIN_ES = {
    Origin.SCRAPER: "Scraper",
    Origin.MANUAL: "Manual",
    Origin.AI_SUGGESTED: "Sugerida por IA",
}

STATUS_ES = {
    Status.UNVERIFIED: "Sin verificar",
    Status.VERIFIED: "Verificada",
    Status.REJECTED: "Rechazada",
}
