"""Validación literal de la cita.

Es el control más importante del pipeline: la cátedra audita que la cita esté
literalmente en la fuente. Se permite normalizar espacios, comillas tipográficas
y guiones (variaciones de codificación, no de contenido), nada más.
"""

from __future__ import annotations

import re
import unicodedata

QUOTE_CHARS = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "«": '"', "»": '"', "‹": "'", "›": "'",
    "`": "'", "´": "'",
}

DASH_CHARS = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-",
    "—": "-", "―": "-", "−": "-",
}

SPACE_CHARS = {
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    " ": " ", " ": " ", " ": " ", " ": " ", "　": " ",
    "​": "", "‌": "", "‍": "", "﻿": "",
}

_TRANSLATION = str.maketrans({**QUOTE_CHARS, **DASH_CHARS, **SPACE_CHARS})
_WS = re.compile(r"\s+")
_ELLIPSIS = re.compile(r"\s*\[?\.\.\.\]?\s*|\s*\[?…\]?\s*")


def normalize_for_match(text: str) -> str:
    """Normalización mínima: no cambia palabras, sólo codificación y espaciado."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_TRANSLATION)
    text = _WS.sub(" ", text)
    return text.strip()


def validate_quote(article_text: str, quote: str) -> bool:
    """True sólo si la cita aparece literalmente en el texto del artículo.

    Admite citas cortadas con elipsis (`...` o `…`): en ese caso se exige que
    cada fragmento aparezca, en orden y sin solaparse, dentro del artículo.
    """
    if not article_text or not quote:
        return False

    haystack = normalize_for_match(article_text)
    needle = normalize_for_match(quote)
    if not needle:
        return False

    if needle in haystack:
        return True

    fragments = [f.strip() for f in _ELLIPSIS.split(needle) if f.strip()]
    if len(fragments) < 2:
        return False

    cursor = 0
    for fragment in fragments:
        if len(fragment) < 25:  # fragmentos muy cortos no prueban nada
            return False
        idx = haystack.find(fragment, cursor)
        if idx == -1:
            return False
        cursor = idx + len(fragment)
    return True


def quote_length_ok(quote: str, min_chars: int = 80, max_chars: int = 600) -> bool:
    return bool(quote) and min_chars <= len(quote.strip()) <= max_chars


def find_quote_offset(article_text: str, quote: str) -> int | None:
    """Posición de la cita en el texto normalizado (útil para mostrar contexto)."""
    haystack = normalize_for_match(article_text)
    needle = normalize_for_match(quote)
    idx = haystack.find(needle)
    return idx if idx >= 0 else None
