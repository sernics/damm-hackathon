# veteran-capture — architecture

How the module turns a 30-second audio from a veteran driver into a
RAG-ready Markdown file that the briefing LLM consumes.

This doc covers the **logic**: what each module does, how data moves
between them, and which decisions are encoded in code. For build status,
commands, and roadmap see [../README.md](../README.md). For design
rationale (why active capture, why per-client markdown, why this
fits the broader DDI challenge) see
[../../cerebro/11_veteran_capture.md](../../cerebro/11_veteran_capture.md).

---

## High-level flow

There are two independent flows that share the same on-disk layout.

### Flow A — Profiling (offline, runs daily / weekly)

```
Raw CSVs (Detalle, Direcciones, Horarios, ...)
        |
        v
mining.io.load_*  ---> normalised pandas frames
        |
        v
mining.customers.build_customer_profiles
mining.affinity.build_driver_customer_affinity
        |
        v
data/profiles/customers.parquet
data/profiles/driver_customer_affinity.parquet
        |
        v
selection.build_priority_queue
        |
        v
data/queues/queue.parquet  (top-N (client, driver) pairs to ask next)
```

Owners: `cli profiles`, `cli select`.

### Flow B — Capture (live, one cycle per audio)

```
Driver opens /capture/{client_id}/{driver_id}
        |
        v  (mic button -> webm blob)
POST /capture/{client_id}/{driver_id}
        |
        v
audio saved to data/audio/   (transient)
        |
        v
capture.stt.transcribe_audio        (OpenAI Whisper)
        |
        v
capture.llm.extract_capture         (Claude Sonnet, tool_use)
        |
        v
capture.llm.moderate_tips           (Claude Haiku, tool_use)
        |
        v
data/captures/<ts>_<client>_<driver>_<id>.json
        |
        v
writer.markdown.write_all_notes     (auto, after each capture)
        |
        v
../dataset/veteran_notes/<client>.md
../dataset/veteran_notes/_manifest.md
../dataset/veteran_notes/manifest.json
        |
        v
Driver sees the thank-you page.
```

Owner: the FastAPI app at `capture.web`.

---

## Module map

```
src/veteran_capture/
+-- __init__.py             package version
+-- paths.py                canonical project paths (PROJECT_ROOT, DATA, etc.)
+-- config.py               pydantic-settings -> Settings (.env aware)
+-- exceptions.py           typed errors (Configuration, Transcription, ...)
+-- logging_setup.py        text or JSON logger, idempotent
+-- cli.py                  argparse entry: profiles | select | serve | write-notes | ...
+-- demo.py                 hand-authored seed captures used for the pitch
+-- mining/
|   +-- io.py               CSV loaders + dtype/dedup hygiene
|   +-- sku.py              is_returnable, cases_equiv, family_from_name
|   +-- customers.py        build_customer_profiles (one row per client)
|   +-- affinity.py         build_driver_customer_affinity (one row per pair)
+-- selection.py            scoring + priority queue
+-- capture/
|   +-- schemas.py          Tip, ExtractedCapture, ModerationVerdict, CaptureResult
|   +-- stt.py              transcribe_audio (Whisper cloud)
|   +-- llm.py              extract_capture + moderate_tips (Claude tool_use)
|   +-- web.py              FastAPI app + routes
|   +-- templates/prompt.html  driver-facing UI
+-- writer/
    +-- aggregate.py        captures -> ClientNotesBundle (per client)
    +-- markdown.py         render markdown KB (per client + index + gaps)
    +-- templates/*.j2      jinja templates
```

---

## Configuration (`config.py`)

Single `Settings` class loaded by `get_settings()` (LRU-cached). Source
priority: env vars > `veteran-capture/.env` > defaults. Everything the
app reads goes through this class — no scattered `os.getenv` calls.

| Field | Default | Why |
|---|---|---|
| `anthropic_api_key` | `""` | Required for extraction + moderation |
| `anthropic_model` | `claude-sonnet-4-6` | Extraction (high-quality JSON) |
| `anthropic_model_moderation` | `claude-haiku-4-5-20251001` | Cheap second pass |
| `openai_api_key` | `""` | Required for Whisper |
| `openai_whisper_model` | `whisper-1` | Cloud STT |
| `data_dir` | `<project>/data` | All transient + intermediate output |
| `raw_csv_dir` | `<repo>/dataset` | Mentor-provided raw CSVs |
| `veteran_notes_dir` | `<repo>/dataset/veteran_notes` | Final RAG output (lives outside this module) |
| `server_host` / `server_port` | `0.0.0.0:8001` | FastAPI bind |
| `log_level` / `log_json` | `INFO` / `False` | Logging shape |

Derived paths are exposed as properties: `profiles_dir`, `queues_dir`,
`audio_dir`. They live under `data_dir` and the module guarantees they
exist before writing into them.

---

## Mining (`mining/`)

### `io.py` — CSV loaders

One function per CSV source, each returning a normalised `DataFrame`
with the column names the rest of the module expects. Hygiene applied:

- Strip whitespace from column headers and string cells.
- Coerce `client_id` to a stable string (avoid float-cast `9100043170.0`).
- Parse `fecha` as UTC datetime.
- Deduplicate `Direcciones.csv` (the source has duplicate `cliente_id`
  rows with conflicting addresses; we keep the most recent).
- Filter zone rows to the operational block (zones starting with
  `DD`, ignoring meta rows).

The detalle frame is the join hub — every other frame is left-joined
onto it via `client_id`.

### `sku.py` — product classification

Three pure functions, all driven by the materials master + naming
conventions on the SKU code:

- `is_returnable(material)` — `True` when the SKU prefix indicates a
  returnable container (`BRL`, `ED`, `TU`, `VO`, `CJ`, `CB`, ...).
- `cases_equiv(qty, umv)` — normalises a delivery line into "cajas
  equivalentes":
  - `CAJ` (cases) -> `qty`
  - `BRL` (barrels) -> `qty * 4` (one barrel ~= 4 cases of payload)
  - `UN` / `BOT` (single units) -> `qty * 0.5`
  - everything else -> `qty`
- `family_from_name(denominacion)` — keyword table mapping product
  descriptions to a coarse family (`cerveza`, `agua`, `refresco`,
  `vino`, `otros`).

These are the only domain-specific transforms in the module. The rest
of the pipeline treats SKUs as opaque strings.

### `customers.py` — per-client profile

`build_customer_profiles(detalle, direcciones, horarios)` produces a
parquet with `PROFILE_COLUMNS`, one row per `client_id`. Highlights of
the aggregations:

| Column | How |
|---|---|
| `n_deliveries` | `nunique(entrega)` |
| `total_cases_equiv` | `sum(cases_equiv)` |
| `pct_returnable_lines` | `# returnable lines / # all lines` |
| `pct_returnable_volume` | `sum(volume_ret) / sum(volume_all)` |
| `delivery_frequency_days` | mean diff between consecutive active dates |
| `top_skus` | top 3 SKUs by line frequency, kept as a list |
| `drivers_seen` | sorted set of repartidor IDs ever seen for this client |
| `client_kind` | `_classify_client`: 10-digit `91xxxxxxxx` -> individual, 6-digit -> chain |
| `has_schedule` | join with `Horarios.csv` |

Address columns (`calle`, `cp`, `poblacion`) prefer `Direcciones.csv`
and fall back to whatever appears in `Detalle.csv` if the master is
missing.

### `affinity.py` — driver-client pairs

`build_driver_customer_affinity(detalle)` produces one row per
`(driver_id, client_id)` with `n_deliveries`, `total_cases_equiv`,
and `last_delivery_date`. Used both by the selection algorithm and by
the capture page (to display "you have covered this client N times").

---

## Selection (`selection.py`)

Decides which `(client_id, driver_id)` pair the cron should query next.
It is a weighted score over six normalised factors. Every factor is in
`[0, 1]`, weights sum to 1.

```
score = w_volume     * volume_score
      + w_gap        * gap_score
      + w_staleness  * staleness_score
      + w_familiarity * familiarity_score
      + w_recency    * recency_score
      + w_complexity * complexity_bonus
```

Default weights (from `ScoringWeights` defaults):

| Weight | Value | Reasoning |
|---|---|---|
| `volume` | 0.30 | Big-volume customers create more downstream value |
| `gap` | 0.30 | Prefer clients we know nothing about |
| `staleness` | 0.10 | Bump clients whose tips are >6 months old |
| `familiarity` | 0.20 | Ask the driver who covers the client most |
| `recency` | 0.05 | Penalise clients we have not delivered to recently |
| `complexity` | 0.05 | Bonus for retornable-heavy and barrel-heavy clients |

### Per-factor formulas

- `volume_score = log1p(total_cases) / log1p(max_total_cases)` —
  log-scaled so a 10x customer is not 10x prioritized.
- `gap_score`: 1.0 with zero tips, linearly down to 0.0 at 5 tips.
- `staleness_score`: 0.0 if last note <30 days, 1.0 if >180 days,
  linear in between.
- `familiarity_score = log1p(driver_deliveries) / log1p(max_pair_deliveries)`.
- `recency_score`: 1.0 if last delivery <30 days, 0.0 if >180 days.
- `complexity_bonus = 0.7 * pct_returnable + 0.3 * has_barrels`.

`build_priority_queue` filters out pairs with fewer than
`min_driver_deliveries` (default 2) so we never ask a driver about a
client they barely know. The output queue carries the components of the
score and a short human-readable `reason` for each row, which makes
debugging the ranking trivial: `cli show-queue --head 15`.

---

## Capture API (`capture/web.py`)

Stateless FastAPI app, no DB, no auth. Built as a function (`create_app`)
so tests can spin a fresh instance, then assigned to `app` for uvicorn.

### Routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/` | Pull the top of the queue, redirect to its capture page |
| `GET` | `/dashboard` | Ops dashboard: paginated, filterable view of the manifest with per-row capture link, copy-to-clipboard, expand-tips, open-MD |
| `GET` | `/api/manifest` | Serve `manifest.json` straight from disk (used by the dashboard's Refresh button) |
| `GET` | `/clients/{client_id}` | Read-only HTML render of `<client_id>.md` |
| `GET` | `/capture/queue` | Return the queue as JSON (debug) |
| `GET` | `/captures` | List the JSON files written so far (debug) |
| `GET` | `/capture/{client_id}/{driver_id}` | Render the driver-facing HTML page |
| `POST` | `/capture/{client_id}/{driver_id}` | Audio upload -> tips JSON |

### Cached reads

Profiles, affinity, queue, and driver-name maps are loaded once into a
module-level `_Cache` and reused. Restart the server to refresh after
re-running profiling.

### Driver-facing page (`templates/prompt.html`)

Rendered with the customer + driver context the page needs:

- The client name, address, zone, mean cases per delivery, frequency
  label, percent retornable.
- Three micro-questions (parking, contact person, operational tricks).
- A single mic button. JavaScript uses `MediaRecorder` to produce a
  webm blob and `POST`s it as multipart `audio` to the same URL.

After submit, the page replaces the recorder with a friendly summary
card showing one row per accepted tip (topic label + text + confidence)
and a footer explaining how many tips were filtered and why.

### POST `/capture/{client_id}/{driver_id}` lifecycle

`_route_capture_audio`, in order:

1. **Validate** the upload. Reject if no file or <200 bytes (likely an
   empty recording).
2. **Save audio** to `data/audio/<ts>-<random>.<ext>`. The extension is
   read from the upload filename and clamped to a known-good list.
3. **Transcribe** with `capture.stt.transcribe_audio`. On failure delete
   the audio and return 502.
4. **Build customer context** from the cached profiles (used by the
   extraction prompt to ground the LLM).
5. **Extract** with `capture.llm.extract_capture` -> `ExtractedCapture`.
   Tool-use forces the model to return a list of structured tips.
6. **Moderate** with `capture.llm.moderate_tips` -> `ModerationVerdict`.
   Tips with PII are redacted in place and returned in `accepted`; tips
   that are insulting, opinion-only, or beyond redacting are returned in
   `rejected`.
7. **Persist** the combined `CaptureResult` as
   `data/captures/<ts>_<client>_<driver>_<rand>.json`.
8. **Delete the audio file** — privacy policy: only the transcript and
   structured tips are kept long-term.
9. **Re-render the markdown KB** via `writer.markdown.write_all_notes`.
   Wrapped in try/except so a render failure does not fail the API
   response.
10. **Return** the `CaptureResult` JSON plus the path to the regenerated
    markdown for debugging. The driver UI uses it to show the friendly
    summary.

---

## Speech-to-text (`capture/stt.py`)

Thin wrapper over the OpenAI Whisper cloud API.

- Accepts the codecs the SDK supports (`webm`, `ogg`, `wav`, `mp3`,
  `m4a`, `mp4`, `mpeg`, `mpga`).
- Default language hint is `es`. The model is multilingual and handles
  the Catalan-Spanish mix the drivers use.
- Returns a stripped string. Empty transcripts raise
  `TranscriptionError` so the caller can fail cleanly.
- Uses the cloud API, not local whisper. Faster setup, more robust on
  hackathon laptops, ~$0.03 for the whole demo.

---

## Extraction + moderation (`capture/llm.py`)

Two separate Anthropic calls. Both use **tool_use** rather than
free-form JSON, so the model is forced to emit a payload that matches
our `Tip` schema. No string parsing, no regex, no JSON.parse retries.

### Extraction (Claude Sonnet)

- System prompt is in Spanish, sets a hard rule: "do not invent
  anything". Each tip has a `topic` (closed enum) and `confidence`
  (`high` / `medium` / `low`).
- Topics: `parking`, `access`, `contact_person`, `barrels`, `empties`,
  `hours`, `warnings`, `other`.
- The user message wraps the customer context (so the model can ground
  references like "Marta" to a known-name role) and the literal
  transcript.
- Tool: `record_tips({ tips: [{topic, text, confidence}] })`. Forced via
  `tool_choice={"type":"tool","name":"record_tips"}`.
- `temperature=0`. Max tokens 1024.
- Empty / whitespace-only transcripts short-circuit to an empty
  `ExtractedCapture` (no API call).

Each tip from the tool call is validated through `Tip.model_validate`.
Malformed tips are dropped with a warning, not surfaced.

### Moderation (Claude Haiku)

A second, cheaper pass. The prompt is structured around a specific
priority: **preserve operational value**. PII is *redacted* in place
rather than rejecting the whole tip. Concretely:

- Phone numbers (9-11 digit runs) -> `[telefono]`.
- Emails -> `[email]`.
- DNIs / NIEs -> `[DNI]`.
- Full names with surnames -> first name only (`"Marta Lopez Ruiz"` ->
  `"Marta"`).
- Private addresses -> `[direccion privada]`.

A tip is rejected only if it has no operational value (insults, pure
opinion, "this place sucks") or nothing useful is left after redacting.

Tool: `record_verdict({ accepted, rejected, notes })`. The `notes`
field is a short summary of what was redacted (e.g. "redactados 2
telefonos") and is shown to the driver on the thank-you page.

Failure mode: if the moderation API call raises, we fail-open with
**all tips in `rejected`**. Better to lose a capture than silently
publish unmoderated content.

---

## Aggregation (`writer/aggregate.py`)

Pure-Python step that turns a list of `CaptureResult` (one per audio)
into one `ClientNotesBundle` per client. No I/O.

Two transformations:

1. **Bucketing.** Within each client, accepted tips are grouped by
   `topic`. Each topic's tips are sorted newest-first.
2. **Consensus detection.** A topic is flagged as `consensus` when two
   or more *distinct* drivers contributed at least one tip on it. The
   markdown template renders a `[consensus: N drivers]` badge so the
   briefing LLM (and humans) can weight those tips higher.

`_accepted_only` falls back to `capture.tips` if the moderation step
was skipped. This matters for unit tests and for any path that builds
a `CaptureResult` without calling the moderator.

`summarise_for_selection` exists as the bridge back into Flow A —
it produces the `notes_summary` frame the selection scorer consumes
(so future queue runs prioritise gaps and stale clients).

---

## Markdown writer (`writer/markdown.py`)

Orchestrates the final render. Reads from disk, writes to disk.

1. Load every `*.json` in `data/captures/` as a `CaptureResult`. Skip
   malformed files with a warning.
2. Load `data/profiles/customers.parquet` for the "quick facts" block.
3. Load driver display names from `Cabecera_Transporte.csv` (best
   effort, fall back to driver IDs).
4. Aggregate captures into per-client bundles.
5. For each bundle, pick the matching customer row, build the
   `_client_facts` dict, and render `templates/client.md.j2`.
6. Build manifest entries for **every active client** (filled and empty).
   For each client we attach: status, tip count, distinct-driver count,
   topics covered, suggested next driver (highest-scoring eligible
   driver from the priority queue), priority score, address, and a
   relative link to the per-client markdown when it exists.
7. Render `_manifest.md` (Markdown table, sorted by priority score
   desc) and `manifest.json` (same data, machine-readable). Old
   `_index.md` and `_gaps.md` are deleted if present.

### Per-client template (`client.md.j2`)

Each rendered file has:

- A header with auto-generation provenance (version + UTC timestamp +
  pointer to the regenerator command).
- "Quick facts" derived purely from the profile parquet (address,
  zone, deliveries, mean cases, retornable share, frequency label,
  top SKUs, drivers seen).
- "Veteran tips" sectioned by topic, in the order defined by
  `TOPIC_ORDER`. Topics with consensus get a badge.
- Each tip line: date — `<driver_id> <driver_name>` (`confidence`):
  text. The confidence and provenance are part of the contract with
  the briefing LLM (it can choose to weight high-confidence,
  multi-driver tips).

### Manifest (`_manifest.md` + `manifest.json`)

Single source of truth for "which client is next, and who do we ask?".

- One row per **active client** (every entry in `customers.parquet`).
- Sorted by priority score descending. The score is computed by
  `selection.build_priority_queue` against all eligible (client, driver)
  pairs and then collapsed to one row per client (the highest-scoring
  driver wins). Clients with no eligible driver still get a fallback
  volume-only score so the manifest is complete.
- Status is `filled` (has at least one captured tip) or `empty`.
- The header highlights the **top N priorities for the next capture
  cycle** (default 20) so a human can read the file like a punch list.
- Each filled row links to the per-client `<id>.md`. Empty rows do not
  link anywhere (the file does not exist yet).
- The matching `manifest.json` mirrors the same data for the cron,
  the dashboard, and any future programmatic consumer. Filled entries
  also carry the **full tips array** (topic, text, confidence,
  driver, capture timestamp, consensus flag), so a single read of
  `manifest.json` gives you everything important: priority order,
  status, and the actual operational content per client. The matching
  `_manifest.md` stays as a TOC and links out to each `<id>.md` for
  the human-readable view.

This single artefact replaces the previous `_index.md` (filled subset)
and `_gaps.md` (empty subset). One file is easier to grep, easier to
diff over time, and shows coverage progress in a single look.

---

## Storage layout (cheat sheet)

| Path | Lifecycle | Owner | Consumed by |
|---|---|---|---|
| `data/profiles/customers.parquet` | Rebuilt by `cli profiles` | `mining.customers` | `selection`, `writer.markdown`, capture page |
| `data/profiles/driver_customer_affinity.parquet` | Rebuilt by `cli profiles` | `mining.affinity` | `selection`, capture page |
| `data/queues/queue.parquet` | Rebuilt by `cli select` | `selection` | `capture.web` (root redirect) |
| `data/captures/*.json` | Append-only (one per audio) | `capture.web` | `writer.markdown` |
| `data/captures/*.seed.json` | Demo seed only, written by `cli seed-demo` | `demo` | `writer.markdown` |
| `data/audio/*` | Transient: deleted after STT | `capture.web` | nothing else |
| `../dataset/veteran_notes/<client>.md` | Rewritten on every capture | `writer.markdown` | **Person B's briefing LLM (RAG)** |
| `../dataset/veteran_notes/_manifest.md` | Rewritten on every capture | `writer.markdown` | Humans, monitoring, cron prioritisation |
| `../dataset/veteran_notes/manifest.json` | Rewritten on every capture | `writer.markdown` | Cron, dashboard, future endpoints |

`data/` lives **inside** the module (private, gitignored). The Markdown
KB lives **outside** (`../dataset/veteran_notes/`) because it is the
public contract with Person B's RAG. Keeping these on different paths
makes the dependency direction obvious.

---

## Privacy

The audio file is the only piece of the pipeline that contains the
driver's voice. It is:

- Saved to `data/audio/` only as a transient buffer for Whisper.
- Deleted as soon as transcription succeeds (or fails — see the
  validation step in `_route_capture_audio`).

Everything downstream is text. PII (phone numbers, emails, DNIs, full
names, private addresses) is redacted by the moderation pass before
the tip ever lands in `data/captures/`. The Markdown output never
contains anything the moderator did not approve.

The driver's display name (e.g. `850018 RUBEN DIAZ`) is shown in the
markdown as provenance. This is by design: tips are more trustworthy
when attributable, and drivers are the legitimate subjects of the data
(operational employees, not consumers). Anonymisation would be
trivial to add (`driver_id` only, drop `driver_name`) but would weaken
the briefing's authority.

---

## Errors and failure modes

| Failure | Behaviour |
|---|---|
| Anthropic API key missing / malformed | `ConfigurationError` at first call (no silent fallback). |
| OpenAI API key missing | Same: `ConfigurationError` from `transcribe_audio`. |
| Whisper returns empty transcript | `TranscriptionError` -> 502 to the driver UI. Audio deleted. |
| Extraction LLM does not call the tool | `ExtractionError` -> 502. |
| One tip from the tool fails `Tip.model_validate` | Dropped with a warning, others kept. |
| Moderation API call fails | Fail-open with all tips in `rejected`. Capture is saved but no tips reach the markdown. |
| Capture JSON is malformed at load time | Skipped with a warning, others rendered. |
| `customers.parquet` missing when capture page is requested | 503 with the "run profiles first" message. |
| `write-notes` raises after a successful capture | Logged, capture stays on disk, response still 200. Re-running `cli write-notes` recovers. |

Every failure path keeps the data on disk so nothing is lost. The
Markdown is always re-derivable from `data/captures/`.

---

## Why these boundaries

A few decisions that look like accidents but are not:

- **Tool-use, not free-form JSON.** Strict schema -> no hallucinated
  fields, no malformed JSON to recover from. The brittleness lives in
  the SDK overload, not in our code.
- **Two LLM calls (extract + moderate), not one.** Cheaper (Haiku for
  the second pass), and easier to swap one model without touching the
  other. Lets us tune the moderation policy independently of the
  extraction policy.
- **Markdown over a database.** The output is a RAG corpus, not an
  application's source of truth. Plain text + git diff + grep beats
  any DB for this use case. The `_index.md` and `_gaps.md` files act
  as cheap APIs for humans and the cron.
- **Pure-Python aggregation.** `writer.aggregate` has no I/O so it can
  be tested with a list of fake `CaptureResult` and zero filesystem
  setup.
- **Per-client one-file-each.** The briefing LLM does retrieval per
  delivery; one file per client is the granularity it needs. No
  monolithic JSON to scan.
- **Audio deleted after STT.** Less attack surface, less compliance
  work, and the transcript is the only artefact the rest of the
  pipeline needs.
