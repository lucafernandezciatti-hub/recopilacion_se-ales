# Recopilación de señales

Herramienta de *foresight* / horizon scanning para construir, diagnosticar y explorar un corpus de señales de futuro.

**Tema núcleo:** la educación primaria en Argentina en 2050.
**Origen:** UTDT · Diseño de Interacción — Diseño de Futuros, Clase 3 ("Detección de señales y drivers").

El objetivo no es un scraper de noticias ni un dashboard genérico. Es un corpus **trazable** —cada señal con su URL y su cita textual, cada cluster navegable hasta las señales que lo componen— y un conjunto de tableros que dicen **dónde está flaco**.

---

## Estado actual

| Fase | Estado |
|---|---|
| 1 · Arquitectura, modelos, SQLite, app ejecutable | ✅ |
| 2 · Ingesta y extracción web (scraper, RSS, fechas, dedupe) | ✅ |
| 3 · Capa de IA con validación estructurada | ✅ |
| 4 · Revisión humana | ✅ |
| 5 · Embeddings, similitud y duplicados semánticos | ⏳ pendiente |
| 6 · Clustering (UMAP + HDBSCAN) y etiquetado | ⏳ pendiente |
| 7 · Mapa semántico | ⏳ pendiente |
| 8 · Diagnóstico de calidad | ✅ (spiderweb, procedencia, novedad, completitud, alertas) |
| 9 · Tests y documentación | ✅ parcial (41 tests) |

**Corpus actual: 49 señales** (ronda 1). Ver *Advertencia sobre las citas* más abajo.

---

## ⚠️ Advertencia sobre las citas de la ronda 1

Las 49 señales de `data/signals_ronda1.json` se recolectaron mediante **lectura remota** de las páginas, no con el scraper del repositorio. Eso significa que **las citas no fueron contrastadas carácter por carácter contra el HTML original**.

Todas están cargadas con `quote_verified = False`. Antes de usarlas para cualquier cosa —y sobre todo antes de que la cátedra las audite— hay que correr:

```bash
python scripts/verify_quotes.py
```

Ese script vuelve a descargar cada URL, extrae el texto y busca la cita literalmente. Reporta tres estados: verificada, cita no literal, o fuente inaccesible. **Una cita que falla no se parchea a mano**: se revisa qué parte del pipeline la produjo (guía Clase 3).

---

## Instalación

Requiere Python 3.11+.

```bash
git clone https://github.com/lucafernandezciatti-hub/recopilacion-de-senales.git
cd recopilacion-de-senales

python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # completar si vas a usar un proveedor de IA real
```

> El scraper necesita **salida a internet sin restricciones**. En entornos con proxy o red cerrada, la descarga de artículos falla con 403 y sólo funcionan las pantallas de análisis.

## Configuración

Todo se edita en YAML, sin tocar código:

| Archivo | Qué define |
|---|---|
| `config/themes.yaml` | tema núcleo, 7 temáticas núcleo y 15 adyacentes, con descripciones que se le pasan al clasificador |
| `config/sources.yaml` | fuentes por cuadrante STEEP (mínimo 5 por cuadrante), feeds RSS, `owner` para agrupar medios del mismo grupo, términos de búsqueda |
| `config/settings.yaml` | timeouts, umbrales de duplicados, parámetros de clustering, umbrales de alerta, tamaño de la muestra de auditoría |

Variables de entorno (`.env`, nunca versionado):

```env
AI_PROVIDER=mock        # anthropic | openai | mock
AI_API_KEY=
AI_MODEL=
DATABASE_URL=           # vacío = SQLite en data/senales.db
```

`mock` permite ejercitar todo el pipeline sin API key: genera salidas de prueba claramente marcadas, no análisis reales.

## Inicializar y correr

```bash
python -c "from src.database.session import init_db; init_db()"
python scripts/load_signals.py data/signals_ronda1.json
streamlit run app.py
```

---

## Pantallas

- **Dashboard** — tamaño del corpus, núcleo vs adyacente, diversidad de fuentes, alertas.
- **Señales** — tabla filtrable y ordenable, buscador, exportación CSV.
- **Revisar** — flujo señal por señal. La IA propone; el grupo corrige. `Utilidad` y `Por qué importa` sólo los escribe el grupo.
- **Calidad del corpus** — spiderweb STEEP, procedencia, novedad, pertinencia × utilidad, completitud.
- **Auditoría** — sorteo aleatorio real de 10 señales y registro de los tres chequeos.
- **Ingesta** — URL manual, lotes, verificación de citas.
- **Configuración** — lectura de los YAML vigentes.

## Diagnósticos implementados

| Vista | Pregunta que responde |
|---|---|
| **Spiderweb STEEP** (dos series: núcleo y adyacente) | ¿Qué cuadrante quedó flaco? ¿Las adyacentes cubren lo que las núcleo no cubren, o repiten la misma forma? |
| **STEEP × fuente** | ¿Hay una fuente que aporta el 40% del corpus? ¿Algún cuadrante depende de una sola? |
| **Temática × STEEP** | ¿Qué combinaciones están sobre o subrepresentadas? |
| **Timeline por fecha de publicación** | ¿Qué tan nuevo es el corpus? (nunca se usa `collected_at` para esto) |
| **Pertinencia × utilidad** | Los cuatro casos conceptuales, con el cuadrante de *periféricas de alto valor* destacado |
| **Completitud y verificación** | ¿Cuánto del corpus tiene cada campo obligatorio? ¿Cuánto revisó una persona? |
| **Alertas** | Umbrales configurables en `settings.yaml`, no verdades universales |

Las fuentes se cuentan por **grupo propietario** (`owner`), no por dominio: diez feeds del mismo grupo mediático son una fuente.

---

## Uso

### Agregar una URL suelta
Pantalla **Ingesta → URL manual**. El pipeline es:

```
URL → normalización → dedupe exacto → descarga → extracción → metadata →
fecha de publicación → fuente → cita → validación literal de la cita →
clasificación IA → guardado → estado = sin verificar → revisión humana
```

### Relevar un lote
```bash
python scripts/harvest.py --urls data/urls_ronda1.txt --out data/candidates.json
python scripts/harvest.py --rss --out data/candidates_rss.json
```

### Verificar las citas
```bash
python scripts/verify_quotes.py            # sólo las no verificadas
python scripts/verify_quotes.py --all      # reverificar todo
python scripts/verify_quotes.py --ids 3 7  # señales puntuales
```

### Tests
```bash
python -m pytest tests/ -q
```

---

## Arquitectura

```
app.py                    Streamlit: todas las pantallas
config/                   themes.yaml · sources.yaml · settings.yaml
scripts/
  harvest.py              descarga y extrae lotes de URLs
  load_signals.py         carga señales clasificadas validando el esquema
  verify_quotes.py        valida cada cita contra el artículo original
src/
  config.py               carga de YAML y entorno
  database/               models.py · session.py · repository.py
  collection/             normalize.py · extractor.py · dates.py · rss.py
  signals/                enums.py · schemas.py · validation.py · service.py
  ai/                     provider.py (Anthropic · OpenAI · Mock) · prompts.py
  analytics/              metrics.py
  visualization/          charts.py
tests/                    41 tests
data/                     corpus versionado + SQLite local (ignorado por git)
```

Decisiones de diseño:

- **SQLite** por defecto, esquema portable a PostgreSQL vía `DATABASE_URL`.
- **Capa de proveedor de IA abstracta**: cambiar de modelo no toca el resto de la app.
- **Prompts versionados** (`signal_classifier_v1`, `cluster_labeler_v1`, `driver_candidate_v1`) fuera del código de interfaz, para poder comparar corridas.
- **Sin base vectorial**: para 500–5.000 señales la búsqueda por fuerza bruta alcanza.
- **Embeddings guardados como JSON** en la tabla `signals`, con modelo y fecha, para poder regenerarlos.

## Principios metodológicos que el código respeta

1. Fecha de publicación ≠ timestamp de relevamiento. Se guardan por separado y la novedad se calcula **siempre** con `publication_date`.
2. La fuente es una variable analítica central, con nombre editorial, dominio y grupo propietario.
3. Pertinencia ≠ utilidad. Son dos campos, dos juicios y dos prompts distintos. Ninguno se infiere del otro.
4. Una señal adyacente puede ser muy útil. Nada penaliza automáticamente lo periférico.
5. Similitud ≠ duplicación irrelevante. Los duplicados semánticos se marcan, nunca se borran solos.
6. Clusters semánticos ≠ temáticas manuales. Coexisten.
7. Cluster ≠ driver.
8. **La IA propone, el humano valida.** Cada campo tiene su par `ai_*`; el clasificador nunca escribe `utility` ni `why_it_matters`.

## Trazabilidad

Requisito duro de la consigna: *ningún dato entra al proyecto sin enlace a su fuente*. Cada señal guarda `link`, `canonical_url`, `quote`, `quote_verified` y la fecha de verificación. La pantalla de auditoría deja registro persistente de cada chequeo en `audit_records`.

---

## Pendiente

- Embeddings, similitud semántica y detección de duplicados (`src/embeddings/`).
- Clustering UMAP + HDBSCAN con configuración reproducible y etiquetado automático.
- Mapa semántico 2D interactivo.
- Vista de candidatos a driver.
- Importación CSV y backup de la base desde la interfaz.
- Llevar el corpus de 49 a 500 señales, cubriendo los cuadrantes flacos que ya marca el diagnóstico.
