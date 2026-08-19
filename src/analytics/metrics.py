"""Métricas de diagnóstico del corpus.

Responde las preguntas de lectura de la guía Clase 3: dónde está flaco el corpus,
de quién depende, qué tan nuevo es y cuánto está efectivamente verificado.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from src.config import settings
from src.signals.enums import Steep

STEEP_ORDER = [s.value for s in Steep]

OBLIGATORY_FIELDS = [
    "publication_date",
    "quote",
    "source_name",
    "theme",
    "steep",
    "relevance",
    "utility",
    "why_it_matters",
]


def signals_to_frame(signals: list) -> pd.DataFrame:
    """Convierte objetos Signal a DataFrame. Una sola vez por render."""
    rows = []
    for s in signals:
        rows.append(
            {
                "id": s.id,
                "title": s.title,
                "original_title": s.original_title,
                "link": s.link,
                "quote": s.quote,
                "quote_verified": bool(s.quote_verified),
                "why_it_matters": s.why_it_matters,
                "ai_why_it_matters": s.ai_why_it_matters,
                "collected_at": s.collected_at,
                "publication_date": s.publication_date,
                "publication_date_confidence": s.publication_date_confidence,
                "theme": s.theme,
                "thematic_relation": s.thematic_relation,
                "steep": s.steep,
                "relevance": s.relevance,
                "utility": s.utility,
                "ai_suggested_utility": s.ai_suggested_utility,
                "source_name": s.source_name,
                "source_domain": s.source_domain,
                "source_owner": s.source_owner or s.source_name,
                "origin": s.origin,
                "status": s.status,
                "cluster_id": s.cluster_id,
                "manual_notes": s.manual_notes,
                "is_demo": bool(s.is_demo),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["publication_date"] = pd.to_datetime(df["publication_date"], errors="coerce")
    return df


# --- cobertura ------------------------------------------------------------
def steep_by_relation(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla STEEP × (núcleo / adyacente) — insumo del spiderweb."""
    base = pd.DataFrame(index=STEEP_ORDER, columns=["core", "adjacent"]).fillna(0).astype(int)
    if df.empty:
        return base
    counts = (
        df.groupby(["steep", "thematic_relation"]).size().unstack(fill_value=0)
    )
    for col in ("core", "adjacent"):
        if col not in counts.columns:
            counts[col] = 0
    counts = counts.reindex(STEEP_ORDER, fill_value=0)
    return counts[["core", "adjacent"]].astype(int)


def steep_by_source(df: pd.DataFrame, by: str = "source_owner") -> pd.DataFrame:
    """Matriz de doble entrada STEEP × fuente (o × grupo propietario)."""
    if df.empty:
        return pd.DataFrame()
    table = df.groupby([by, "steep"]).size().unstack(fill_value=0)
    table = table.reindex(columns=STEEP_ORDER, fill_value=0)
    return table.sort_values(by=list(table.columns), ascending=False)


def theme_by_steep(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(["theme", "steep"]).size().unstack(fill_value=0)
        .reindex(columns=STEEP_ORDER, fill_value=0)
    )


# --- diversidad de fuentes ------------------------------------------------
def source_diversity(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"n_sources": 0, "n_owners": 0, "n_domains": 0, "top": [], "top5_share": 0.0}

    owner_counts = df["source_owner"].value_counts()
    total = len(df)
    top5 = owner_counts.head(5)
    hhi = float(((owner_counts / total) ** 2).sum())
    return {
        "n_sources": int(df["source_name"].nunique()),
        "n_owners": int(owner_counts.size),
        "n_domains": int(df["source_domain"].nunique()),
        "top": [(name, int(count), count / total) for name, count in top5.items()],
        "top1_share": float(owner_counts.iloc[0] / total),
        "top3_share": float(owner_counts.head(3).sum() / total),
        "top5_share": float(top5.sum() / total),
        "hhi": hhi,
    }


# --- novedad --------------------------------------------------------------
def novelty(df: pd.DataFrame) -> dict[str, Any]:
    """Novedad basada SIEMPRE en publication_date, nunca en collected_at."""
    windows = settings()["quality_alerts"]["novelty_windows_days"]
    if df.empty:
        return {"buckets": {}, "missing": 0, "missing_share": 0.0}

    today = pd.Timestamp(datetime.now(timezone.utc).date())
    dated = df.dropna(subset=["publication_date"])
    missing = len(df) - len(dated)

    buckets: dict[str, int] = {}
    if not dated.empty:
        age = (today - dated["publication_date"]).dt.days
        previous = 0
        for window in windows:
            buckets[f"últimos {window} días"] = int(((age >= 0) & (age <= window)).sum() - previous)
            previous = int(((age >= 0) & (age <= window)).sum())
        buckets["más antiguo"] = int((age > max(windows)).sum())

    return {
        "buckets": buckets,
        "missing": int(missing),
        "missing_share": missing / len(df),
        "median_age_days": (
            float((today - dated["publication_date"]).dt.days.median()) if not dated.empty else None
        ),
        "min_date": dated["publication_date"].min() if not dated.empty else None,
        "max_date": dated["publication_date"].max() if not dated.empty else None,
    }


# --- completitud y verificación ------------------------------------------
def completeness(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {field: 0.0 for field in OBLIGATORY_FIELDS}
    out = {}
    for field in OBLIGATORY_FIELDS:
        if field not in df.columns:
            out[field] = 0.0
            continue
        filled = df[field].notna() & (df[field].astype(str).str.strip() != "")
        out[field] = float(filled.mean())
    return out


def verification(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"reviewed_share": 0.0, "quote_verified_share": 0.0, "by_status": {}}
    return {
        "reviewed_share": float((df["status"] != "unverified").mean()),
        "quote_verified_share": float(df["quote_verified"].mean()),
        "by_status": df["status"].value_counts().to_dict(),
    }


# --- alertas --------------------------------------------------------------
def quality_alerts(df: pd.DataFrame) -> list[dict[str, str]]:
    """Advertencias configurables. No son verdades universales: son umbrales."""
    cfg = settings()["quality_alerts"]
    alerts: list[dict[str, str]] = []
    if df.empty:
        return alerts

    total = len(df)
    diversity = source_diversity(df)

    if diversity["top1_share"] > cfg["max_share_top_source"]:
        name = diversity["top"][0][0]
        alerts.append({
            "level": "alta",
            "text": (
                f"{diversity['top1_share']:.0%} del corpus proviene de una sola fuente "
                f"({name}). El corpus se parece a su línea editorial."
            ),
        })
    if diversity["top3_share"] > cfg["max_share_top3_sources"]:
        alerts.append({
            "level": "alta",
            "text": f"{diversity['top3_share']:.0%} del corpus proviene de sólo tres fuentes.",
        })

    steep_share = df["steep"].value_counts(normalize=True)
    for steep in STEEP_ORDER:
        share = float(steep_share.get(steep, 0.0))
        if share < cfg["min_share_per_steep"]:
            alerts.append({
                "level": "alta" if share == 0 else "media",
                "text": (
                    f"Sólo {share:.0%} de las señales corresponde al cuadrante {steep}. "
                    "¿No pasa nada ahí, o no fuimos a buscar?"
                ),
            })

    missing_date = float(df["publication_date"].isna().mean())
    if missing_date > cfg["max_share_missing_publication_date"]:
        alerts.append({
            "level": "alta",
            "text": (
                f"{missing_date:.0%} de las señales no tiene fecha de publicación. "
                "Sin ella no hay análisis de novedad posible."
            ),
        })

    high_rel = float((df["relevance"] >= 8).mean())
    if high_rel > cfg["max_share_relevance_8_10"]:
        alerts.append({
            "level": "media",
            "text": (
                f"El {high_rel:.0%} de las señales tiene pertinencia 8-10. "
                "Revisar posible sesgo del clasificador."
            ),
        })

    adjacent = float((df["thematic_relation"] == "adjacent").mean())
    if adjacent < cfg["min_share_adjacent"]:
        alerts.append({
            "level": "media",
            "text": (
                f"Sólo {adjacent:.0%} de las señales es adyacente. El corpus puede estar "
                "confirmando el mapa mental en vez de ampliarlo."
            ),
        })

    unverified_quotes = int((~df["quote_verified"]).sum())
    if unverified_quotes:
        alerts.append({
            "level": "alta",
            "text": (
                f"{unverified_quotes} de {total} señales tienen la cita SIN verificar "
                "contra la fuente original. Correr scripts/verify_quotes.py."
            ),
        })

    no_wim = int(df["why_it_matters"].isna().sum())
    if no_wim:
        alerts.append({
            "level": "media",
            "text": (
                f"{no_wim} señales no tienen 'por qué importa' escrito por el grupo. "
                "La sugerencia de IA no reemplaza esa decisión."
            ),
        })

    return alerts


def corpus_summary(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "total": len(df),
        "core": int((df["thematic_relation"] == "core").sum()) if not df.empty else 0,
        "adjacent": int((df["thematic_relation"] == "adjacent").sum()) if not df.empty else 0,
        "themes": int(df["theme"].nunique()) if not df.empty else 0,
        "diversity": source_diversity(df),
        "novelty": novelty(df),
        "completeness": completeness(df),
        "verification": verification(df),
    }
