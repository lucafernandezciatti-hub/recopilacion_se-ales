"""Detección de fecha de publicación con nivel de confianza.

Principio 1 de la guía: fecha de publicación ≠ timestamp de relevamiento.
Si no se puede determinar con confianza, se guarda None y se registra el problema.
Nunca se inventa una fecha.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

MIN_YEAR = 1990
MAX_FUTURE_DAYS = 2


@dataclass(slots=True)
class DateResult:
    value: date | None
    confidence: str | None  # high | medium | low
    method: str | None
    note: str | None = None


def _parse(raw: str | None) -> date | None:
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = dateparser.parse(str(raw).strip(), fuzzy=False)
    except (ValueError, OverflowError, TypeError):
        return None
    if parsed is None:
        return None
    value = parsed.date()
    today = datetime.now(timezone.utc).date()
    if value.year < MIN_YEAR:
        return None
    if (value - today).days > MAX_FUTURE_DAYS:
        return None
    return value


def _jsonld_dates(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    keys = ("datePublished", "dateCreated", "uploadDate", "dateModified")

    def walk(node) -> None:
        if isinstance(node, dict):
            for key in keys:
                if key in node and isinstance(node[key], str):
                    found.append(node[key])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(tag.string or "{}"))
        except (json.JSONDecodeError, TypeError):
            continue
    return found


TEXT_PATTERNS = [
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"),
]

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _from_text(text: str) -> date | None:
    head = text[:1500]
    for pattern in TEXT_PATTERNS:
        match = pattern.search(head)
        if not match:
            continue
        groups = match.groups()
        try:
            if len(groups) == 3 and groups[1].lower() in MESES:
                value = date(int(groups[2]), MESES[groups[1].lower()], int(groups[0]))
            elif pattern.pattern.startswith(r"\b(\d{4})"):
                value = date(int(groups[0]), int(groups[1]), int(groups[2]))
            else:
                value = date(int(groups[2]), int(groups[1]), int(groups[0]))
        except ValueError:
            continue
        today = datetime.now(timezone.utc).date()
        if MIN_YEAR <= value.year and (value - today).days <= MAX_FUTURE_DAYS:
            return value
    return None


def extract_publication_date(
    html: str | None,
    text: str | None = None,
    trafilatura_date: str | None = None,
) -> DateResult:
    """Orden de preferencia: JSON-LD > OpenGraph/meta > trafilatura > <time> > texto."""
    if html:
        soup = BeautifulSoup(html, "html.parser")

        for raw in _jsonld_dates(soup):
            value = _parse(raw)
            if value:
                return DateResult(value, "high", "jsonld")

        meta_props = [
            ("property", "article:published_time"),
            ("property", "og:published_time"),
            ("property", "og:article:published_time"),
            ("name", "publish-date"),
            ("name", "publication_date"),
            ("name", "date"),
            ("name", "pubdate"),
            ("itemprop", "datePublished"),
            ("name", "DC.date.issued"),
            ("name", "dcterms.created"),
            ("name", "sailthru.date"),
            ("name", "parsely-pub-date"),
        ]
        for attr, key in meta_props:
            tag = soup.find("meta", attrs={attr: key})
            if tag and tag.get("content"):
                value = _parse(tag["content"])
                if value:
                    return DateResult(value, "high", f"meta:{key}")

        time_tag = soup.find("time", attrs={"datetime": True})
        if time_tag:
            value = _parse(time_tag["datetime"])
            if value:
                return DateResult(value, "medium", "time_tag")

    if trafilatura_date:
        value = _parse(trafilatura_date)
        if value:
            return DateResult(value, "medium", "trafilatura")

    if text:
        value = _from_text(text)
        if value:
            return DateResult(value, "low", "text_pattern")

    return DateResult(None, None, None, note="fecha de publicación no determinable")
