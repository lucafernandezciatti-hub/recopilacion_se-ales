"""Gráficos de diagnóstico (Plotly)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.analytics.metrics import STEEP_ORDER
from src.signals.enums import STEEP_ES, UTILITY_ES

PALETTE = {
    "core": "#1f6f6b",
    "adjacent": "#d98c3f",
    "grid": "#d9dde1",
    "text": "#2b3138",
}
SEQUENTIAL = "Teal"


def _steep_labels() -> list[str]:
    return [STEEP_ES[s] for s in STEEP_ORDER]


def spiderweb_steep(table: pd.DataFrame) -> go.Figure:
    """Radar de 5 ejes STEEP con dos series superpuestas: núcleo y adyacente."""
    labels = _steep_labels()
    fig = go.Figure()
    for column, name, color in (
        ("core", "Núcleo", PALETTE["core"]),
        ("adjacent", "Adyacente", PALETTE["adjacent"]),
    ):
        values = table[column].tolist()
        fig.add_trace(
            go.Scatterpolar(
                r=values + values[:1],
                theta=labels + labels[:1],
                name=name,
                fill="toself",
                opacity=0.55,
                line={"color": color, "width": 2},
            )
        )
    fig.update_layout(
        polar={"radialaxis": {"visible": True, "gridcolor": PALETTE["grid"]}},
        showlegend=True,
        margin={"l": 60, "r": 60, "t": 40, "b": 40},
        height=430,
    )
    return fig


def heatmap(table: pd.DataFrame, title: str, x_title: str, y_title: str) -> go.Figure:
    fig = px.imshow(
        table,
        text_auto=True,
        aspect="auto",
        color_continuous_scale=SEQUENTIAL,
        labels={"x": x_title, "y": y_title, "color": "señales"},
    )
    fig.update_layout(
        title=title,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        height=max(320, 26 * len(table) + 120),
        coloraxis_showscale=False,
    )
    return fig


def source_distribution(df: pd.DataFrame, by: str = "source_owner", top: int = 20) -> go.Figure:
    counts = df[by].value_counts().head(top).sort_values()
    share = counts / len(df)
    fig = go.Figure(
        go.Bar(
            x=counts.values,
            y=counts.index,
            orientation="h",
            marker_color=PALETTE["core"],
            text=[f"{c} ({s:.0%})" for c, s in zip(counts.values, share.values)],
            textposition="outside",
        )
    )
    fig.update_layout(
        margin={"l": 10, "r": 40, "t": 30, "b": 10},
        height=max(300, 24 * len(counts) + 80),
        xaxis_title="señales",
        yaxis_title=None,
    )
    return fig


def publication_timeline(df: pd.DataFrame, freq: str = "M") -> go.Figure:
    """Histograma temporal por FECHA DE PUBLICACIÓN, nunca por collected_at."""
    dated = df.dropna(subset=["publication_date"])
    if dated.empty:
        return go.Figure()
    grouped = (
        dated.set_index("publication_date").resample(freq).size().reset_index(name="señales")
    )
    fig = px.bar(grouped, x="publication_date", y="señales", color_discrete_sequence=[PALETTE["core"]])
    fig.update_layout(
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        height=320,
        xaxis_title="fecha de publicación",
    )
    return fig


def relevance_histogram(df: pd.DataFrame) -> go.Figure:
    fig = px.histogram(
        df, x="relevance", nbins=10, color_discrete_sequence=[PALETTE["core"]]
    )
    fig.update_layout(
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        height=300,
        xaxis={"dtick": 1, "title": "pertinencia"},
        bargap=0.05,
    )
    return fig


def utility_distribution(df: pd.DataFrame, column: str = "utility") -> go.Figure:
    order = list(UTILITY_ES.keys())
    counts = df[column].value_counts().reindex([o.value for o in order], fill_value=0)
    fig = go.Figure(
        go.Bar(
            x=[UTILITY_ES[o] for o in order],
            y=counts.values,
            marker_color=PALETTE["core"],
            text=counts.values,
            textposition="outside",
        )
    )
    fig.update_layout(margin={"l": 10, "r": 10, "t": 30, "b": 10}, height=300)
    return fig


def relevance_vs_utility(df: pd.DataFrame, column: str = "utility") -> go.Figure:
    """Visualización central: los cuatro casos conceptuales.

    El cuadrante interesante es baja/media pertinencia + alta utilidad:
    señales periféricas de alto valor prospectivo.
    """
    order = [o.value for o in UTILITY_ES]
    working = df.dropna(subset=[column, "relevance"]).copy()
    if working.empty:
        return go.Figure()
    working["utilidad"] = working[column].map({o.value: UTILITY_ES[o] for o in UTILITY_ES})
    table = (
        working.groupby(["relevance", column]).size().unstack(fill_value=0)
        .reindex(columns=order, fill_value=0)
    )
    table.columns = [UTILITY_ES[c] for c in UTILITY_ES]
    fig = px.imshow(
        table.T,
        text_auto=True,
        aspect="auto",
        color_continuous_scale=SEQUENTIAL,
        labels={"x": "pertinencia", "y": "utilidad", "color": "señales"},
    )
    fig.add_shape(
        type="rect", x0=-0.5, x1=5.5, y0=-0.5, y1=1.5,
        line={"color": PALETTE["adjacent"], "width": 3}, fillcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        title="Pertinencia × utilidad — el recuadro marca las periféricas de alto valor",
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        height=340,
        coloraxis_showscale=False,
    )
    return fig


def category_bar(df: pd.DataFrame, column: str, labels: dict | None = None) -> go.Figure:
    counts = df[column].value_counts()
    names = [labels.get(i, i) if labels else i for i in counts.index]
    fig = go.Figure(
        go.Bar(
            x=names, y=counts.values, marker_color=PALETTE["core"],
            text=[f"{v} ({v/len(df):.0%})" for v in counts.values], textposition="outside",
        )
    )
    fig.update_layout(margin={"l": 10, "r": 10, "t": 30, "b": 10}, height=320)
    return fig
