"""Descarga y extracción de contenido de artículos.

Devuelve siempre un `ExtractionResult`: una URL que falla no rompe el batch.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urljoin

import httpx
import trafilatura
from bs4 import BeautifulSoup

from src.collection.dates import extract_publication_date
from src.collection.normalize import domain_of, normalize_url, text_hash, url_hash
from src.config import settings, source_registry

logger = logging.getLogger(__name__)

_WS = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


@dataclass(slots=True)
class ExtractionResult:
    url: str
    canonical_url: str | None = None
    url_hash: str | None = None
    domain: str | None = None
    source_name: str | None = None
    source_owner: str | None = None
    original_title: str | None = None
    author: str | None = None
    language: str | None = None
    raw_html: str | None = None
    cleaned_text: str | None = None
    text_hash: str | None = None
    publication_date: date | None = None
    publication_date_confidence: str | None = None
    publication_date_method: str | None = None
    method: str | None = None
    success: bool = False
    error: str | None = None
    paragraphs: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    text = _WS.sub(" ", text)
    text = _BLANKS.sub("\n\n", text)
    return text.strip()


def _paragraphs(text: str, min_chars: int = 90) -> list[str]:
    out: list[str] = []
    for block in text.split("\n"):
        block = block.strip()
        if len(block) >= min_chars:
            out.append(block)
    return out


def _resolve_source(domain: str, html_title: str | None, soup: BeautifulSoup | None):
    registry = source_registry()
    entry = registry.get(domain)
    if entry:
        return entry.get("name"), entry.get("owner")

    site_name = None
    if soup is not None:
        tag = soup.find("meta", attrs={"property": "og:site_name"})
        if tag and tag.get("content"):
            site_name = tag["content"].strip()
    return site_name or domain, site_name or domain


def fetch(url: str, client: httpx.Client | None = None) -> tuple[str | None, str | None]:
    """Devuelve (html, error)."""
    cfg = settings()["scraping"]
    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            follow_redirects=True,
            timeout=cfg["timeout_seconds"],
            headers={
                "User-Agent": cfg["user_agent"],
                "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
            },
        )
    try:
        for attempt in range(cfg["max_retries"] + 1):
            try:
                response = client.get(url)
                if response.status_code >= 400:
                    return None, f"HTTP {response.status_code}"
                ctype = response.headers.get("content-type", "")
                if "html" not in ctype and "xml" not in ctype and ctype:
                    return None, f"content-type no soportado: {ctype}"
                return response.text, None
            except httpx.HTTPError as exc:
                if attempt >= cfg["max_retries"]:
                    return None, f"{type(exc).__name__}: {exc}"
        return None, "sin respuesta"
    finally:
        if owns_client:
            client.close()


def extract(url: str, client: httpx.Client | None = None) -> ExtractionResult:
    cfg = settings()["scraping"]
    try:
        normalized = normalize_url(url)
    except ValueError as exc:
        return ExtractionResult(url=url, success=False, error=f"URL inválida: {exc}")

    result = ExtractionResult(url=normalized, domain=domain_of(normalized))
    html, error = fetch(normalized, client=client)
    if html is None:
        result.error = error
        result.method = "httpx"
        return result

    result.raw_html = html
    soup = BeautifulSoup(html, "html.parser")

    canonical_tag = soup.find("link", rel=lambda v: v and "canonical" in v)
    if canonical_tag and canonical_tag.get("href"):
        try:
            result.canonical_url = normalize_url(urljoin(normalized, canonical_tag["href"]))
        except ValueError:
            result.canonical_url = None
    result.url_hash = url_hash(result.canonical_url or normalized)

    og_title = soup.find("meta", attrs={"property": "og:title"})
    result.original_title = (
        (og_title["content"].strip() if og_title and og_title.get("content") else None)
        or (soup.title.get_text(strip=True) if soup.title else None)
    )

    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        with_metadata=False,
        url=normalized,
    )
    method = "trafilatura"
    if not extracted or len(extracted) < cfg["min_text_chars"]:
        fallback = "\n".join(
            p.get_text(" ", strip=True) for p in soup.find_all(["p", "li", "h2", "h3"])
        )
        if len(fallback) > len(extracted or ""):
            extracted, method = fallback, "bs4_fallback"

    if not extracted or len(extracted) < cfg["min_text_chars"]:
        result.method = method
        result.error = (
            f"texto insuficiente ({len(extracted or '')} chars; "
            f"mínimo {cfg['min_text_chars']}) — posible paywall o render JS"
        )
        return result

    result.cleaned_text = _clean(extracted)
    result.paragraphs = _paragraphs(result.cleaned_text)
    result.text_hash = text_hash(result.cleaned_text)
    result.method = method

    meta = trafilatura.extract_metadata(html)
    traf_date = getattr(meta, "date", None) if meta else None
    if meta:
        result.author = getattr(meta, "author", None)
        result.language = getattr(meta, "language", None)

    date_result = extract_publication_date(html, result.cleaned_text, traf_date)
    result.publication_date = date_result.value
    result.publication_date_confidence = date_result.confidence
    result.publication_date_method = date_result.method

    result.source_name, result.source_owner = _resolve_source(
        result.domain or "", result.original_title, soup
    )
    result.success = True
    return result
