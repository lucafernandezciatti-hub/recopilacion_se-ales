"""Recopilación de señales — herramienta de horizon scanning.

    streamlit run app.py
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.analytics import metrics
from src.config import all_themes, core_topic, settings, theme_names
from src.database import repository as repo
from src.database.session import get_session, init_db
from src.signals.enums import (
    RELATION_ES,
    STATUS_ES,
    STEEP_ES,
    UTILITY_ES,
    Status,
    Steep,
    ThematicRelation,
    Utility,
)
from src.visualization import charts

load_dotenv()

st.set_page_config(page_title="Recopilación de señales", page_icon="◎", layout="wide")


# --------------------------------------------------------------------------
# datos
# --------------------------------------------------------------------------
@st.cache_data(ttl=30, show_spinner=False)
def load_frame() -> pd.DataFrame:
    with get_session() as session:
        return metrics.signals_to_frame(repo.list_signals(session))


def refresh() -> None:
    load_frame.clear()


init_db()
df_all = load_frame()


# --------------------------------------------------------------------------
# filtros
# --------------------------------------------------------------------------
def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.title("◎ Señales")
    st.sidebar.caption(core_topic())

    if df.empty:
        st.sidebar.info("Corpus vacío.")
        return df

    with st.sidebar.expander("Filtros", expanded=True):
        themes = st.multiselect("Temática", sorted(df["theme"].dropna().unique()))
        relations = st.multiselect(
            "Relación temática",
            [r.value for r in ThematicRelation],
            format_func=lambda v: RELATION_ES[ThematicRelation(v)],
        )
        steeps = st.multiselect(
            "STEEP", [s.value for s in Steep], format_func=lambda v: STEEP_ES[Steep(v)]
        )
        sources = st.multiselect("Fuente", sorted(df["source_owner"].dropna().unique()))
        statuses = st.multiselect(
            "Estado", [s.value for s in Status], format_func=lambda v: STATUS_ES[Status(v)]
        )
        rel_min, rel_max = st.slider("Pertinencia", 1, 10, (1, 10))
        only_unverified_quote = st.checkbox("Sólo con cita sin verificar")

    out = df.copy()
    if themes:
        out = out[out["theme"].isin(themes)]
    if relations:
        out = out[out["thematic_relation"].isin(relations)]
    if steeps:
        out = out[out["steep"].isin(steeps)]
    if sources:
        out = out[out["source_owner"].isin(sources)]
    if statuses:
        out = out[out["status"].isin(statuses)]
    out = out[out["relevance"].between(rel_min, rel_max) | out["relevance"].isna()]
    if only_unverified_quote:
        out = out[~out["quote_verified"]]

    st.sidebar.metric("Señales en vista", f"{len(out)} / {len(df)}")
    return out


df = sidebar_filters(df_all)

PAGES = [
    "Dashboard",
    "Señales",
    "Revisar",
    "Clusters",
    "Calidad del corpus",
    "Auditoría",
    "Ingesta",
    "Configuración",
]
page = st.sidebar.radio("Pantalla", PAGES, label_visibility="collapsed")


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
if page == "Dashboard":
    st.title("Dashboard del corpus")

    if df_all.empty:
        st.warning("No hay señales cargadas. Usá la pantalla **Ingesta** para empezar.")
        st.stop()

    summary = metrics.corpus_summary(df)
    cols = st.columns(5)
    cols[0].metric("Señales", summary["total"])
    cols[1].metric("Núcleo / Adyacente", f"{summary['core']} / {summary['adjacent']}")
    cols[2].metric("Fuentes (grupos)", summary["diversity"]["n_owners"])
    cols[3].metric("Citas verificadas", f"{summary['verification']['quote_verified_share']:.0%}")
    cols[4].metric("Revisadas", f"{summary['verification']['reviewed_share']:.0%}")

    alerts = metrics.quality_alerts(df)
    if alerts:
        st.subheader("Alertas de calidad")
        for alert in alerts:
            (st.error if alert["level"] == "alta" else st.warning)(alert["text"])

    left, right = st.columns(2)
    with left:
        st.subheader("Cobertura STEEP — núcleo vs adyacente")
        st.plotly_chart(
            charts.spiderweb_steep(metrics.steep_by_relation(df)), use_container_width=True
        )
    with right:
        st.subheader("Distribución por fuente")
        st.plotly_chart(charts.source_distribution(df), use_container_width=True)


# --------------------------------------------------------------------------
# Señales
# --------------------------------------------------------------------------
elif page == "Señales":
    st.title("Señales")
    if df.empty:
        st.info("Sin resultados para los filtros actuales.")
        st.stop()

    query = st.text_input("Buscar (título, cita, fuente)")
    view = df
    if query:
        mask = (
            view["title"].str.contains(query, case=False, na=False)
            | view["quote"].str.contains(query, case=False, na=False)
            | view["source_name"].str.contains(query, case=False, na=False)
        )
        view = view[mask]

    table = view[
        [
            "id", "title", "publication_date", "theme", "thematic_relation", "steep",
            "relevance", "utility", "source_name", "status", "quote_verified", "link",
        ]
    ].rename(
        columns={
            "id": "#", "title": "Título de señal", "publication_date": "Publicación",
            "theme": "Temática", "thematic_relation": "Relación", "steep": "STEEP",
            "relevance": "Pertinencia", "utility": "Utilidad", "source_name": "Fuente",
            "status": "Estado", "quote_verified": "Cita ✓", "link": "Link",
        }
    )
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Link", display_text="abrir")},
    )

    st.download_button(
        "Exportar CSV (vista actual)",
        view.to_csv(index=False).encode("utf-8"),
        file_name=f"senales_{datetime.now(timezone.utc):%Y%m%d}.csv",
        mime="text/csv",
    )


# --------------------------------------------------------------------------
# Revisar
# --------------------------------------------------------------------------
elif page == "Revisar":
    st.title("Revisión humana")
    st.caption("La IA propone; el grupo valida. `Utilidad` y `Por qué importa` son decisión humana.")

    if df.empty:
        st.info("Sin señales para revisar con los filtros actuales.")
        st.stop()

    ids = df["id"].tolist()
    if "review_idx" not in st.session_state:
        st.session_state.review_idx = 0
    st.session_state.review_idx = min(st.session_state.review_idx, len(ids) - 1)
    current_id = ids[st.session_state.review_idx]

    nav = st.columns([1, 1, 2, 3])
    if nav[0].button("← Anterior", use_container_width=True):
        st.session_state.review_idx = max(0, st.session_state.review_idx - 1)
    if nav[1].button("Siguiente →", use_container_width=True):
        st.session_state.review_idx = min(len(ids) - 1, st.session_state.review_idx + 1)
    with nav[2].form("goto_signal_form", clear_on_submit=False, border=False):
        goto_cols = st.columns([2, 1])
        goto_id = goto_cols[0].number_input(
            "Ir a señal #", min_value=1, step=1, value=current_id, label_visibility="collapsed"
        )
        goto_submitted = goto_cols[1].form_submit_button("Ir", use_container_width=True)
    if goto_submitted:
        if goto_id in ids:
            st.session_state.review_idx = ids.index(goto_id)
        else:
            st.warning(
                f"La señal #{goto_id} no existe, o quedó fuera de los filtros actuales de la barra lateral."
            )
    nav[3].caption(f"Señal {st.session_state.review_idx + 1} de {len(ids)}")

    signal_id = ids[st.session_state.review_idx]
    with get_session() as session:
        signal = repo.get_signal(session, signal_id)
        if signal is None:
            st.error("Señal no encontrada.")
            st.stop()

        st.subheader(signal.title)
        meta = st.columns(4)
        meta[0].caption(f"**Fuente**\n\n{signal.source_name}")
        meta[1].caption(f"**Publicación**\n\n{signal.publication_date or '— sin fecha —'}")
        meta[2].caption(f"**Relevado**\n\n{signal.collected_at:%Y-%m-%d}")
        meta[3].link_button("Abrir fuente ↗", signal.link, use_container_width=True)

        if signal.original_title:
            st.caption(f"Titular original: *{signal.original_title}*")

        if signal.quote_verified:
            st.success("Cita verificada literalmente contra el original.")
        else:
            st.error(
                "Cita SIN verificar contra el original. Correr `scripts/verify_quotes.py` "
                "antes de dar esta señal por buena."
            )
        st.markdown(f"> {signal.quote or '— sin cita —'}")

        if signal.ai_reasoning_short:
            with st.expander("Razonamiento de la IA (propuesta, no conclusión)"):
                st.write(signal.ai_reasoning_short)
                st.caption(
                    f"modelo: {signal.ai_model or 'n/d'} · prompt: {signal.ai_prompt_version}"
                )

        with st.form(f"review_{signal_id}"):
            new_title = st.text_input("Título de señal", signal.title)

            row1 = st.columns(3)
            theme_options = theme_names()
            current_theme = signal.theme if signal.theme in theme_options else theme_options[0]
            new_theme = row1[0].selectbox(
                "Temática", theme_options, index=theme_options.index(current_theme)
            )
            relation_values = [r.value for r in ThematicRelation]
            new_relation = row1[1].selectbox(
                "Relación temática",
                relation_values,
                index=relation_values.index(signal.thematic_relation or "core"),
                format_func=lambda v: RELATION_ES[ThematicRelation(v)],
            )
            steep_values = [s.value for s in Steep]
            new_steep = row1[2].selectbox(
                "STEEP",
                steep_values,
                index=steep_values.index(signal.steep or "Social"),
                format_func=lambda v: STEEP_ES[Steep(v)],
            )

            row2 = st.columns(2)
            new_relevance = row2[0].slider("Pertinencia (proximidad temática)", 1, 10, signal.relevance or 5)
            utility_values = [u.value for u in Utility]
            suggested = signal.ai_suggested_utility
            row2[1].caption(
                f"Sugerencia de la IA: **{UTILITY_ES[Utility(suggested)]}**"
                if suggested else "Sin sugerencia de IA"
            )
            new_utility = row2[1].radio(
                "Utilidad (potencia especulativa) — decisión del grupo",
                utility_values,
                index=utility_values.index(signal.utility) if signal.utility else 1,
                format_func=lambda v: UTILITY_ES[Utility(v)],
                horizontal=True,
            )

            if signal.ai_why_it_matters:
                st.caption(f"Sugerencia de la IA: *{signal.ai_why_it_matters}*")
            new_wim = st.text_area(
                "Por qué importa (dos líneas, decisión del grupo)",
                signal.why_it_matters or "",
                height=90,
            )
            new_notes = st.text_area("Notas internas", signal.manual_notes or "", height=70)
            reviewer = st.text_input("Revisado por", signal.reviewed_by or "")

            actions = st.columns(3)
            save = actions[0].form_submit_button("Guardar cambios", use_container_width=True)
            verify = actions[1].form_submit_button("Verificar ✓", use_container_width=True)
            reject = actions[2].form_submit_button("Rechazar ✕", use_container_width=True)

            if save or verify or reject:
                signal.title = new_title
                signal.theme = new_theme
                signal.thematic_relation = new_relation
                signal.steep = new_steep
                signal.relevance = new_relevance
                signal.utility = new_utility
                signal.why_it_matters = new_wim.strip() or None
                signal.manual_notes = new_notes.strip() or None
                if verify:
                    if not signal.quote_verified:
                        st.warning(
                            "Marcada como verificada pero la cita sigue sin contrastarse "
                            "contra el original."
                        )
                    signal.status = Status.VERIFIED.value
                if reject:
                    signal.status = Status.REJECTED.value
                repo.touch_reviewed(signal, reviewer or None)
                refresh()
                st.success("Guardado.")


# --------------------------------------------------------------------------
# Clusters
# --------------------------------------------------------------------------
elif page == "Clusters":
    st.title("Análisis de oportunidad")
    st.caption(
        "Clusters semánticos sobre un plano de novedad × volumen (guía Clase 4). "
        "El gráfico ordena el corpus; la selección de qué mirar la hace el grupo."
    )

    with get_session() as session:
        run = repo.active_run(session)
        cluster_rows = repo.clusters_for_run(session, run.id) if run else []
        labels = {c.cluster_index: c.label for c in cluster_rows if c.label}
        pending_embeddings = len(repo.signals_without_embedding(session))

    top = st.columns([2, 2, 3])
    if run:
        top[0].metric("Clusters", run.n_clusters)
        top[1].metric("Sin cluster (ruido)", run.n_noise)
        top[2].caption(
            f"Corrida #{run.id} · {run.n_signals} señales · modelo `{run.embedding_model}`"
        )
    else:
        top[0].info("Todavía no se corrió el clustering.")

    if pending_embeddings:
        st.warning(f"{pending_embeddings} señales sin embedding calculado.")

    if st.button("Recalcular embeddings y clustering", type="primary"):
        progress_bar = st.progress(0.0, text="Calculando embeddings...")
        try:
            with st.spinner("Esto puede tardar varios minutos la primera vez..."):
                with get_session() as session:
                    from src.embeddings.clustering import run_clustering
                    from src.embeddings.model import compute_missing_embeddings

                    compute_missing_embeddings(
                        session,
                        progress=lambda done, total: progress_bar.progress(
                            done / total, text=f"Embeddings {done}/{total}"
                        ),
                    )
                    progress_bar.progress(1.0, text="Clusterizando...")
                    outcome = run_clustering(session)
            progress_bar.empty()
            refresh()
            st.success(
                f"{outcome.n_clusters} clusters sobre {outcome.n_signals} señales "
                f"({outcome.n_noise} quedaron sin cluster)."
            )
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            progress_bar.empty()
            st.error(f"Falló el clustering: {exc}")

    frame = metrics.cluster_opportunity_frame(df_all, labels)
    if frame.empty:
        st.info("Sin clusters todavía. Usá el botón de arriba para calcularlos.")
        st.stop()

    st.plotly_chart(charts.opportunity_bubbles(frame), use_container_width=True)
    st.caption(
        "**Tamaño = robustez** (fuentes distintas). En el cuadrante *Borde* leé primero el "
        "tamaño y después la posición: una burbuja chica ahí puede ser una sola voz o una "
        "campaña de prensa, no una señal débil válida."
    )

    st.divider()
    st.subheader("Abrir un cluster")
    st.caption("Requisito de trazabilidad: cada cluster abre sus señales, cada señal abre su URL.")

    options = frame["cluster_id"].tolist()
    chosen = st.selectbox(
        "Cluster",
        options,
        format_func=lambda cid: (
            f"{frame.loc[frame['cluster_id'] == cid, 'etiqueta'].iloc[0]} "
            f"({frame.loc[frame['cluster_id'] == cid, 'volumen'].iloc[0]} señales)"
        ),
    )

    row = frame[frame["cluster_id"] == chosen].iloc[0]
    stats = st.columns(4)
    stats[0].metric("Volumen", row["volumen"])
    stats[1].metric("Robustez", f"{row['robustez']} fuentes")
    stats[2].metric("Novedad media", f"{row['novedad']:%Y-%m-%d}")
    stats[3].metric("STEEP dominante", STEEP_ES.get(Steep(row["steep"]), "—") if row["steep"] else "—")

    members = df_all[df_all["cluster_id"] == chosen]
    for _, signal_row in members.iterrows():
        with st.expander(f"#{signal_row['id']} · {signal_row['title']}"):
            st.caption(
                f"{signal_row['source_name']} · "
                f"{signal_row['publication_date']:%Y-%m-%d}"
                if pd.notna(signal_row["publication_date"])
                else f"{signal_row['source_name']} · sin fecha"
            )
            st.markdown(f"> {signal_row['quote'] or '— sin cita —'}")
            st.markdown(f"[Abrir fuente ↗]({signal_row['link']})")

    noise = df_all[df_all["cluster_id"].isna()]
    if not noise.empty:
        st.divider()
        st.caption(
            f"{len(noise)} señales quedaron fuera de todo cluster. HDBSCAN no fuerza a que "
            "todo entre en un grupo: son señales sueltas que todavía no forman un fenómeno."
        )


# --------------------------------------------------------------------------
# Calidad del corpus
# --------------------------------------------------------------------------
elif page == "Calidad del corpus":
    st.title("Calidad del corpus")
    if df.empty:
        st.info("Sin datos.")
        st.stop()

    summary = metrics.corpus_summary(df)

    st.subheader("Alertas")
    alerts = metrics.quality_alerts(df)
    if not alerts:
        st.success("Ninguna alerta con los umbrales configurados.")
    for alert in alerts:
        (st.error if alert["level"] == "alta" else st.warning)(alert["text"])

    st.divider()
    st.subheader("Cobertura — spiderweb STEEP")
    table = metrics.steep_by_relation(df)
    left, right = st.columns([3, 2])
    left.plotly_chart(charts.spiderweb_steep(table), use_container_width=True)
    display = table.rename(columns={"core": "Núcleo", "adjacent": "Adyacente"})
    display.index = [STEEP_ES[Steep(i)] for i in display.index]
    right.dataframe(display, use_container_width=True)
    right.caption(
        "¿Qué cuadrante quedó flaco? ¿Es porque ahí no pasa nada, o porque no fuimos a buscar? "
        "Si la serie adyacente repite la forma de la núcleo, las adyacentes no eran adyacentes."
    )

    st.divider()
    st.subheader("Procedencia — STEEP × fuente")
    st.caption("Se agrupa por grupo propietario: diez feeds del mismo medio son una fuente.")
    st.plotly_chart(
        charts.heatmap(
            metrics.steep_by_source(df), "Señales por fuente y cuadrante", "STEEP", "Fuente"
        ),
        use_container_width=True,
    )
    diversity = summary["diversity"]
    cols = st.columns(4)
    cols[0].metric("Grupos distintos", diversity["n_owners"])
    cols[1].metric("Dominios distintos", diversity["n_domains"])
    cols[2].metric("Top 1", f"{diversity['top1_share']:.0%}")
    cols[3].metric("Top 5", f"{diversity['top5_share']:.0%}")

    st.divider()
    st.subheader("Temática × STEEP")
    st.plotly_chart(
        charts.heatmap(metrics.theme_by_steep(df), "", "STEEP", "Temática"),
        use_container_width=True,
    )

    st.divider()
    st.subheader("Novedad — por fecha de publicación")
    novelty = summary["novelty"]
    cols = st.columns(4)
    cols[0].metric("Sin fecha", f"{novelty['missing']} ({novelty['missing_share']:.0%})")
    cols[1].metric("Edad mediana (días)", f"{novelty['median_age_days']:.0f}" if novelty["median_age_days"] else "—")
    cols[2].metric("Más antigua", f"{novelty['min_date']:%Y-%m-%d}" if novelty["min_date"] is not None else "—")
    cols[3].metric("Más reciente", f"{novelty['max_date']:%Y-%m-%d}" if novelty["max_date"] is not None else "—")
    st.plotly_chart(charts.publication_timeline(df), use_container_width=True)

    st.divider()
    st.subheader("Pertinencia y utilidad")
    cols = st.columns(2)
    cols[0].plotly_chart(charts.relevance_histogram(df), use_container_width=True)
    has_human_utility = df["utility"].notna().any()
    cols[1].plotly_chart(
        charts.utility_distribution(df, "utility" if has_human_utility else "ai_suggested_utility"),
        use_container_width=True,
    )
    if not has_human_utility:
        cols[1].caption("Mostrando la **sugerencia de IA**: todavía no hay utilidad asignada por el grupo.")
    st.plotly_chart(
        charts.relevance_vs_utility(df, "utility" if has_human_utility else "ai_suggested_utility"),
        use_container_width=True,
    )

    st.divider()
    st.subheader("Completitud")
    completeness = pd.Series(summary["completeness"], name="completitud").to_frame()
    completeness["completitud"] = completeness["completitud"].map(lambda v: f"{v:.0%}")
    st.dataframe(completeness, use_container_width=True)


# --------------------------------------------------------------------------
# Auditoría
# --------------------------------------------------------------------------
elif page == "Auditoría":
    st.title("Auditoría de 10 al azar")
    st.caption(
        "Por cada señal sorteada verificar: (a) el link abre; (b) la cita está literalmente "
        "en el original; (c) el 'por qué importa' no le atribuye a la fuente algo que no dice. "
        "Si falla una, no se parchea el dato: se revisa el método."
    )

    if df_all.empty:
        st.info("Sin señales.")
        st.stop()

    sample_size = settings()["audit"]["sample_size"]
    if st.button("Sortear muestra"):
        st.session_state.audit_batch = str(uuid.uuid4())[:8]
        st.session_state.audit_ids = random.sample(
            df_all["id"].tolist(), min(sample_size, len(df_all))
        )

    if "audit_ids" not in st.session_state:
        st.info("Sorteá una muestra para empezar. El muestreo es aleatorio real, sin selección.")
        st.stop()

    st.caption(f"Lote de auditoría `{st.session_state.audit_batch}`")
    with get_session() as session:
        for signal_id in st.session_state.audit_ids:
            signal = repo.get_signal(session, signal_id)
            if signal is None:
                continue
            with st.container(border=True):
                st.markdown(f"**#{signal.id} — {signal.title}**")
                st.markdown(f"> {signal.quote or '— sin cita —'}")
                st.link_button("Abrir fuente ↗", signal.link)
                cols = st.columns(4)
                link_ok = cols[0].checkbox("El link abre", key=f"a_link_{signal.id}")
                quote_ok = cols[1].checkbox("Cita literal", key=f"a_quote_{signal.id}")
                claim_ok = cols[2].checkbox("No inventa", key=f"a_claim_{signal.id}")
                notes = cols[3].text_input("Nota", key=f"a_note_{signal.id}")
                if cols[3].button("Registrar", key=f"a_save_{signal.id}"):
                    repo.add_audit_record(
                        session,
                        batch_id=st.session_state.audit_batch,
                        signal_id=signal.id,
                        link_ok=link_ok,
                        quote_ok=quote_ok,
                        claim_ok=claim_ok,
                        notes=notes or None,
                    )
                    st.success("Registrado.")


# --------------------------------------------------------------------------
# Ingesta
# --------------------------------------------------------------------------
elif page == "Ingesta":
    st.title("Ingesta de señales")
    st.info(
        "El scraping necesita salida a internet. Corré la app en tu máquina "
        "(no en un entorno con red restringida) para que funcione."
    )

    tab_url, tab_batch, tab_verify = st.tabs(["URL manual", "Lote de URLs", "Verificar citas"])

    with tab_url:
        url = st.text_input("URL del artículo")
        if st.button("Procesar URL") and url:
            from src.ai.provider import get_provider
            from src.signals.enums import Origin
            from src.signals.service import ingest_url

            with st.spinner("Descargando, extrayendo y clasificando..."):
                with get_session() as session:
                    outcome = ingest_url(session, url, get_provider(), origin=Origin.MANUAL)
            refresh()
            if outcome.status == "created":
                st.success(f"Señal #{outcome.signal_id} creada.")
            elif outcome.status == "duplicate":
                st.warning(f"Ya está en el corpus (señal #{outcome.signal_id}).")
            else:
                st.error(f"{outcome.status}: {outcome.reason}")

    with tab_batch:
        st.markdown(
            "```bash\n"
            "python scripts/harvest.py --urls data/urls_ronda1.txt --out data/candidates.json\n"
            "python scripts/harvest.py --rss --out data/candidates_rss.json\n"
            "```"
        )
        st.caption("El harvest deja los artículos extraídos listos para clasificar.")

    with tab_verify:
        st.markdown("```bash\npython scripts/verify_quotes.py\n```")
        unverified = int((~df_all["quote_verified"]).sum()) if not df_all.empty else 0
        st.metric("Señales con cita sin verificar", unverified)


# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------
elif page == "Configuración":
    st.title("Configuración")
    st.caption("Se edita en `config/*.yaml`. Reiniciá la app para tomar los cambios.")

    st.subheader("Tema núcleo")
    st.write(core_topic())

    st.subheader("Temáticas")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Temática": t["name"],
                    "Relación": RELATION_ES[ThematicRelation(t["default_relation"])],
                    "Descripción": " ".join(t.get("description", "").split()),
                }
                for t in all_themes()
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Umbrales de alerta")
    st.json(settings()["quality_alerts"])
