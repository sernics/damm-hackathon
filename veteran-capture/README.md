# veteran-capture

Active capture of tacit driver knowledge: cron picks (client, driver) pairs, sends a short prompt to a veteran driver, the driver replies with a voice message, the system transcribes it and writes structured Markdown notes per client. The Markdown is the RAG source for the briefing LLM.

> Full spec lives in [`../cerebro/11_veteran_capture.md`](../cerebro/11_veteran_capture.md). Read that first if you want the design rationale. This README is just the build plan.
>
> For a 5-minute narrative explainer of how the whole module works see [`docs/OVERVIEW.md`](docs/OVERVIEW.md). For the code-level walkthrough see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## How this fits in the project

The team's overall plan (`../app/ROADMAP.md`):

| Person | Component | Output |
|---|---|---|
| Person A | Clusters + truck-fill algorithm | Structured cargo data per (cluster, truck) |
| Person B | Briefing LLM (RAG-based) | The augmented albaran the driver takes |
| **Us** | **Veteran capture (this module)** | **Markdown knowledge base per client, fed to Person B's RAG** |
| Person D | Dashboard | Visual UI |

We are upstream of Person B. Our output is one of two RAG sources their briefing LLM consumes:
1. Patterns from 889 historical transports (Person B builds this themselves).
2. **Per-client veteran tips** (this module produces this).

---

## What we're building, in 5 components

1. **Mining.** Extract per-customer and per-driver profiles from the raw CSVs (frequency, volume, retornable rate, driver-customer affinity). Output: `dataset/profiles/{customers,drivers}.parquet`.
2. **Selection algorithm.** Score (client, driver) pairs by priority and pick the next N to query. Output: a queue.
3. **Capture webapp.** Minimal FastAPI + HTML page with one big mic button. Driver opens link on phone, records 30 s of audio, hits send.
4. **Extraction.** Whisper transcribes the audio. Anthropic API extracts structured tips as JSON (with strict schema and a moderation pass).
5. **Writer.** Markdown writer produces one `.md` per client, plus a single `_manifest.md` (and matching `manifest.json`) listing every active client in priority order with status, suggested next driver, and a link to the per-client tips file. Aggregates multi-driver consensus.

---

## Build phases (~12-16 h of focused work)

| Phase | Hours | What | Acceptance |
|---|---:|---|---|
| 0 | 0.5 | Python venv + deps installed (fastapi, whisper, anthropic, jinja2, python-multipart) | `python -c "import fastapi, anthropic, whisper, pandas"` works |
| 1 | 2.0 | Customer profile + driver-customer affinity from CSVs | `dataset/profiles/customers.parquet` exists with 1.203 rows and the priority columns |
| 2 | 1.5 | Selection algorithm produces a ranked queue of (client, driver) pairs | Top 10 of the queue look sensible (high-volume clients with experienced drivers) |
| 3 | 3.5 | FastAPI server + HTML page (mic button, upload, prompt template) | Run locally, hit `/capture/{client_id}/{driver_id}`, record audio, see it land on disk |
| 4 | 2.5 | Whisper STT + Anthropic JSON extraction with moderation | Audio in -> structured tips JSON out, hallucination-free |
| 5 | 2.5 | Markdown writer per client + index + gaps + multi-driver consensus | `dataset/veteran_notes/{client_id}.md` produced, schema matches cerebro/11 |
| 6 | 1.5 | Demo seed (10-20 mock notes) + E2E run | Demo can be done end-to-end on stage |

---

## File layout (what we'll create here)

```
veteran-capture/
+- README.md                     <- this file
+- pyproject.toml or requirements.txt
+- .env.example                  <- ANTHROPIC_API_KEY etc.
+- src/
|  +- __init__.py
|  +- profiles.py                <- phase 1: customer + driver profiles
|  +- selection.py               <- phase 2: priority queue
|  +- capture/
|  |  +- web.py                  <- phase 3: FastAPI app
|  |  +- templates/
|  |  |  +- prompt.html          <- driver-facing page
|  +- extract/
|  |  +- stt.py                  <- phase 4: Whisper wrapper
|  |  +- llm.py                  <- phase 4: Anthropic extraction prompt
|  |  +- moderate.py             <- phase 4: content moderation pass
|  +- writer/
|  |  +- markdown.py             <- phase 5: per-client + index + gaps
|  |  +- consensus.py            <- phase 5: multi-driver aggregation
|  +- main.py                    <- CLI entry / cron trigger
+- tests/                        <- if we have time, basic unit tests
+- demo/
   +- seed_notes.json            <- 10-20 mock veteran tips for the pitch
   +- run_e2e.sh                 <- demo runner
```

Output (lives outside this folder, fed to Person B):

```
../dataset/veteran_notes/        <- the actual Markdown KB
../dataset/profiles/             <- intermediate parquet files
```

---

## Stack

- **Python 3.14** (system interpreter), local venv at `veteran-capture/.venv`.
- **FastAPI + uvicorn** for the capture endpoint.
- **HTML + vanilla JS** with `MediaRecorder` API. No frontend framework. Goal: works on any phone in any browser.
- **OpenAI Whisper (local)** for STT. Multilingual, handles Catalan-Spanish mix.
- **Anthropic Claude** for tip extraction (Sonnet 4.6 by default, can downgrade to Haiku for cheap moderation).
- **Pandas** for CSV mining and profile building.
- **Jinja2** for both HTML templates (capture page) and Markdown templates (per-client output).

---

## What this module does NOT do

- It does not build the briefing itself (Person B's job).
- It does not run the route or pack the truck (Person A's job).
- It does not host a dashboard (Person D's job).
- It does not communicate with drivers via WhatsApp / Telegram in the demo: the demo uses a webapp link. Production channel is a real follow-up question to the mentor (`../cerebro/QUESTIONS.md` Q49).

---

## Coordination touchpoints

- **With Person B** (briefing LLM): align Markdown schema and confirm RAG ingestion strategy. 30-min sync at start of phase 5.
- **With Person A** (clusters + truck-fill): no integration needed — both feed Person B independently.
- **With Person D** (dashboard): possibly surface a "tips coverage" widget showing how many clients have notes. Optional, last priority.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Cold start (no real driver tips on day 1) | Seed 10-20 mock tips for the demo. Frame the captured tips as "the system gets smarter over time". |
| Whisper STT inaccurate on noisy audio | Test early with realistic samples (driver in cabin, ambient noise). Fall back to OpenAI API Whisper if local model is too slow. |
| Inappropriate / offensive content in audio | Two-pass LLM: extraction first, then moderation. Hold flagged tips for manual review. |
| Hallucination from Claude | Strict JSON schema + temperature 0 + provenance attached to each tip. No free-form text in the KB. |
| Drivers ignore the prompts | We do not solve this in the demo. Frame in pitch: "active capture is the long-term play, day-1 fallback is mock + seed". |

---

## Demo story (90 seconds during the pitch)

1. We pick one customer with an existing tip and show the briefing for them — it cites the tip with provenance ("Pedro suele cubrir esta ruta — dijo: aparcar en la rotonda").
2. We trigger the capture flow live: pick another customer, generate the prompt, record a 30-second audio on a phone, watch the system transcribe and add the tip.
3. We re-generate the briefing — now it includes the new tip.
4. Money line: *"DDI lleva décadas perdiendo conocimiento operativo cuando un veterano se jubila. Nuestro sistema lo captura cada día. En 12 meses tendréis una base de 1.203 fichas operativas que hoy no existen ni siquiera en SAP."*

---

## How to run it

> All commands assume you are inside `veteran-capture/`.
> Phases 0-5 are all done; pipeline is working end-to-end on real APIs.

### One-time setup

```bash
make install-dev                     # creates .venv, installs deps + dev tools
cp .env.example .env                 # then edit .env with real ANTHROPIC + OPENAI keys
.venv/bin/python -c "from veteran_capture.config import get_settings; \
    s = get_settings(); print('anthropic:', 'OK' if s.anthropic_api_key.startswith('sk-ant') else 'MISSING'); \
    print('openai:', 'OK' if s.openai_api_key.startswith('sk-') else 'MISSING')"
```

### Daily / on-demand commands

```bash
# 1. Build customer + driver-customer profiles from raw CSVs (-> data/profiles/*.parquet)
.venv/bin/python -m veteran_capture.cli profiles

# 2. Build the priority queue of (client, driver) pairs to ask next (-> data/queues/queue.parquet)
.venv/bin/python -m veteran_capture.cli select --top-n 100
.venv/bin/python -m veteran_capture.cli show-queue --head 15

# 3. Launch the capture webapp
.venv/bin/python -m veteran_capture.cli serve            # listens on 0.0.0.0:8001
# Open http://localhost:8001/                            -> redirects to top-priority capture page
# Open http://localhost:8001/dashboard                   -> ops dashboard (paginated, filterable, copy-link per row)
# Open http://localhost:8001/capture/<client>/<driver>   -> direct capture link
# POST audio -> Whisper -> Claude extraction -> moderation -> JSON saved to data/captures/

# 4. Aggregate captures into the per-client markdown KB (-> ../dataset/veteran_notes/)
.venv/bin/python -m veteran_capture.cli write-notes

# 5. Demo seed (hand-authored realistic captures for the pitch)
.venv/bin/python -m veteran_capture.cli seed-demo --overwrite
.venv/bin/python -m veteran_capture.cli write-notes      # then re-render the KB
```

### Sanity / dev commands

```bash
make smoke         # imports + settings load (no API calls)
make test          # pytest
make lint          # ruff
make typecheck     # mypy strict
make fmt           # ruff format
make clean         # delete venv + caches
```

### Where the outputs land

| Path | What it is | Consumed by |
|---|---|---|
| `data/profiles/customers.parquet` | One row per active customer with operational features | This module + Person B |
| `data/profiles/driver_customer_affinity.parquet` | (driver, customer) -> # deliveries | This module |
| `data/queues/queue.parquet` | Top-N (client, driver) pairs to query, with priority score | The capture webapp |
| `data/captures/*.json` | One per audio submission. Transcript + structured tips + moderation verdict | This module's writer |
| `data/audio/*` | Transient audio uploads. **Deleted after transcription succeeds** | — |
| `../dataset/veteran_notes/<client_id>.md` | RAG-ready Markdown per client | **Person B's briefing LLM** |
| `../dataset/veteran_notes/_manifest.md` | Single ordered table of every active client (filled + empty) with priority score and suggested next driver | Humans / monitoring / cron |
| `../dataset/veteran_notes/manifest.json` | Same data as `_manifest.md` in machine-readable form | Cron, dashboard, future endpoints |
