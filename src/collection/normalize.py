"""Normalización de URLs y hashing, para detección de duplicados exactos."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Parámetros de tracking que no cambian el contenido apuntado.
TRACKING_PREFIXES = ("utm_", "pk_", "mc_", "hsa_", "vero_", "_hs")
TRACKING_EXACT = {
    "fbclid", "gclid", "dclid", "msclkid", "igshid", "mkt_tok", "ref", "ref_src",
    "referrer", "source", "spm", "cmpid", "ncid", "smid", "s", "at_medium",
    "at_campaign", "sh", "share", "amp", "__twitter_impression",
}

_WS = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    """Devuelve una forma canónica estable de la URL.

    - fuerza esquema https cuando el original es http
    - baja host a minúsculas y quita `www.`
    - elimina parámetros de tracking y ordena el resto
    - quita fragmento y barra final redundante
    """
    if not url or not url.strip():
        raise ValueError("URL vacía")

    url = url.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url

    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"Esquema no soportado: {parts.scheme}")

    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        raise ValueError(f"URL sin host: {url}")

    netloc = host
    if parts.port and parts.port not in (80, 443):
        netloc = f"{host}:{parts.port}"

    query_pairs = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() not in TRACKING_EXACT
        and not any(k.lower().startswith(p) for p in TRACKING_PREFIXES)
    ]
    query = urlencode(sorted(query_pairs))

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    if not path:
        path = "/"

    return urlunparse(("https", netloc, path, "", query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def domain_of(url: str) -> str:
    host = (urlparse(normalize_url(url)).hostname or "").lower()
    return host


def text_hash(text: str | None) -> str | None:
    """Hash del texto normalizado, para detectar republicaciones idénticas."""
    if not text:
        return None
    normalized = _WS.sub(" ", text).strip().lower()
    if len(normalized) < 200:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
