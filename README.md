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
| 5 · Embeddings | ✅ (`src/embeddings/model.py`) |
| 6 · Clustering (UMAP + HDBSCAN) y etiquetado | ✅ (23 clusters sobre 500 señales) |
| 7 · Mapa semántico 2D | ⏳ pendiente |
| 8 · Diagnóstico de calidad | ✅ (spiderweb, procedencia, novedad, completitud, alertas) |
| 9 · Tests y documentación | ✅ parcial (41 tests) |

**Corpus actual: 500 señales** (ronda 1: 49, rondas 2-8: 151 y rondas 9-11: 100 cada una). Desde la ronda 2 en adelante se recolectó con el scraper real (`harvest.py`) y clasificación de IA en sesión (sin API paga), con cita verificada automáticamente contra el texto extraído — no tienen el problema de la ronda 1. Las rondas 9, 10 y 11 pasaron `verify_quotes.py`: 300 verificadas, 0 citas fallidas y 0 fuentes inaccesibles.

**Ronda 9 cargada:** IDs 201-300, con 30 señales STEEP Ambiental y refuerzo de
las temáticas débiles. Las citas están verificadas; las decisiones humanas de
`Utilidad`, `Por qué importa` y estado final siguen pendientes de revisión.

**Ronda 10 cargada:** IDs 301-400, con refuerzo de clima y ambiente,
alfabetización, primera infancia, federalismo, pantallas y salud mental. Incluye
fuentes oficiales, organismos internacionales y 42 registros científicos de
Europe PMC. Las 100 citas están verificadas; `Utilidad`, `Por qué importa` y el
estado final siguen pendientes de revisión humana.

**Ronda 11 cargada:** IDs 401-500, balanceada para corregir el corpus: 35 señales
Ambientales, 33 Económicas, 28 Tecnológicas y 4 Políticas, sin agregar señales
Sociales. Reúne 20 propietarios de fuente y evita fuentes gubernamentales
argentinas. El corpus completo queda en 118 Sociales, 100 Políticas y 94 en cada
uno de los otros tres cuadrantes. Las 100 citas están verificadas; `Utilidad`,
`Por qué importa` y el estado final siguen pendientes de revisión humana.

---

## ⚠️ Advertencia sobre las citas de la ronda 1

Las 49 señales de `data/signals_ronda1.json` se recolectaron mediante **lectura remota** de las páginas, no con el scraper del repositorio. La verificación posterior encontró 32 citas literales, 9 no literales y 8 fuentes inaccesibles. Las 17 pendientes no deben usarse como evidencia hasta resolverlas.

Para repetir la auditoría:

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
python scripts/load_signals.py data/signals_ronda2.json
python scripts/load_signals.py data/signals_ronda3.json
python scripts/load_signals.py data/signals_ronda4.json
python scripts/load_signals.py data/signals_ronda5.json
python scripts/load_signals.py data/signals_ronda6.json
python scripts/load_signals.py data/signals_ronda7.json
python scripts/load_signals.py data/signals_ronda8.json
python scripts/load_signals.py data/signals_ronda9.json
python scripts/load_signals.py data/signals_ronda10.json
python scripts/load_signals.py data/signals_ronda11.json
python scripts/verify_quotes.py
python scripts/cluster_signals.py    # embeddings (la 1ra vez baja el modelo)
python scripts/import_clusters.py    # clusters de referencia del grupo
streamlit run app.py
```

---

## Pantallas

- **Dashboard** — tamaño del corpus, núcleo vs adyacente, diversidad de fuentes, alertas.
- **Señales** — tabla filtrable y ordenable, buscador, exportación CSV.
- **Revisar** — flujo señal por señal, con salto directo por número de señal. La IA propone; el grupo corrige. `Utilidad` y `Por qué importa` sólo los escribe el grupo.
- **Clusters** — análisis de oportunidad (guía Clase 4): novedad × volumen, tamaño = robustez, color = STEEP dominante. Cada cluster abre sus señales y cada señal su URL.
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

### Unificar las revisiones del equipo

La base local no se versiona, así que las decisiones humanas (`utilidad`,
`por qué importa`, estado) no viajan solas. Cada persona exporta a **su propio**
archivo —un archivo por persona evita conflictos de git— y todas importan:

```bash
python scripts/export_reviews.py --autor luca   # -> data/reviews_luca.json
git add data/reviews_luca.json && git commit -m "revisiones luca" && git push
```

```bash
git pull
python scripts/import_reviews.py --dry-run      # ver qué haría, sin tocar nada
python scripts/import_reviews.py
```

Las señales se emparejan por `url_hash` —igual que los clusters—, nunca por `id`:
el id es el orden de inserción de cada base local, así que si alguien cargó las
rondas en otro orden su señal 42 no es la misma que la tuya. Si a alguien le llega
una revisión de una señal que no tiene, el import la reporta por su URL y sigue.

Conviene **repartir los clusters sin superposición**: si nadie revisa las mismas
señales, no hay desacuerdos posibles. Si igual dos personas califican distinto la
misma señal, el import **no elige por su cuenta**: reporta el desacuerdo y deja
esa señal intacta. Discutir si una señal es *muy útil* o *pobre* es el trabajo de
la Clase 4, no un dato a resolver pisando el de otra. Una vez acordado:

```bash
python scripts/import_reviews.py --forzar luca
```

### Unificar los clusters del equipo

Los clusters **no se recalculan en cada máquina**: se calculan una vez y se
versionan. El clustering es *global* —HDBSCAN agrupa por densidad sobre el corpus
entero—, así que dos personas obtienen particiones distintas, no "la misma con
ruido", si difieren en una señal, si cargaron las rondas en otro orden (el orden
de las filas cambia la proyección de UMAP) o si tienen otra versión de
`umap-learn` o `scikit-learn`.

Quien define la clusterización del grupo la exporta una vez:

```bash
python scripts/cluster_signals.py               # sólo esta persona
python scripts/export_clusters.py --autor luca  # -> data/clusters.json
git add data/clusters.json && git commit -m "clusters de referencia" && git push
```

El resto sólo importa:

```bash
git pull
python scripts/import_clusters.py --dry-run     # ver qué haría, sin tocar nada
python scripts/import_clusters.py
```

Las señales se emparejan por `url_hash` —sale de la URL normalizada y vale lo
mismo en cualquier máquina—, nunca por `id`, que es el orden de inserción de cada
base local. Si a alguien le faltan señales, el import las reporta
(`faltan-en-tu-corpus`) y aplica el resto: nunca inventa una asignación.

Después de importar, **no correr `cluster_signals.py`**: recalcula y pisa lo
importado. Sólo lo corre quien exporta, cuando el corpus crece.

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
  cluster_labels.json     etiquetas de cluster escritas por el grupo (SÍ versionado)
```

Decisiones de diseño:

- **SQLite** por defecto, esquema portable a PostgreSQL vía `DATABASE_URL`.
- **Capa de proveedor de IA abstracta**: cambiar de modelo no toca el resto de la app.
- **Prompts versionados** (`signal_classifier_v1`, `cluster_labeler_v1`, `driver_candidate_v1`) fuera del código de interfaz, para poder comparar corridas.
- **Sin base vectorial**: para 500–5.000 señales la búsqueda por fuerza bruta alcanza.
- **Embeddings guardados como JSON** en la tabla `signals`, con modelo y fecha, para poder regenerarlos.
- **Etiquetas de cluster fuera de la base**, en `data/cluster_labels.json`. La base local no se versiona: si las etiquetas vivieran sólo ahí, cada recálculo y cada clon del repo dejaría los clusters numerados y sin descripción. El clustering las reaplica por `cluster_index` al terminar.

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
