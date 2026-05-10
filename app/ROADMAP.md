# Smart Truck — 2-person roadmap (v2: dual AI stack)

> Hackathon Interhack BCN 2026 — Damm "Smart Truck" challenge.
> Full problem context lives in [`../cerebro/`](../cerebro/). Read
> [`../cerebro/00_brief.md`](../cerebro/00_brief.md) and
> [`../cerebro/01_context.md`](../cerebro/01_context.md) before this file.

---

## What we are building (one paragraph)

A multi-agent AI dispatcher for a beer delivery truck. The system takes a
day's route + cargo and produces (a) a 3D physical load plan, (b) a
conversational explanation grounded in historical data and warehouse photos,
and (c) an augmented printed albaran the driver can take into the cabin. Five
Claude agents specialise in different operational roles and stream their
reasoning live to a 3D-truck UI that the user can scrub through, talk to,
and override.

The pitch line: **"Our tool makes any driver perform like a veteran on any
route"** — backed by RAG over 889 real historical transports and computer
vision over 47 real warehouse photos.

---

## Why this is genuinely useful (not AI-for-AI's-sake)

Every AI piece below answers a concrete pain DDI named in the brief or the
mentor sessions. Pinning each:

| AI piece | Real pain it solves |
|---|---|
| Veteran RAG over 889 transports | Mentor: drivers are optimal only on their own route; substitutes underperform. RAG transfers the tacit pattern. |
| Inspector vision over 47 photos | Mentor: customer interior distance and warehouse layout are not in the data. Vision extracts what is in the photos. |
| Packer agent with explanation | Brief evaluation criterion: explainability (15% creativity). Plain-language "why this layout". |
| Router agent with what-if | Brief: route + load co-optimisation. The agent re-plans in seconds when the dispatcher asks "what if I move client X". |
| Dispatcher orchestrator | Mentor: the driver only ever sees the printed albaran. The dispatcher generates the augmented albaran. |

Nothing is bolted-on. Each agent maps to a role a human plays at DDI today.

---

## Architecture: 5 agents, 2 tracks, one stream

```
                      User (browser)
                        |    ^
                  prompt|    | streamed reasoning (SSE)
                        v    |
              +-----------------------+
              |    DISPATCHER  Sonnet | <--- system prompt + cached LoadPlan
              |   (orchestrator)      |
              +-----------------------+
                  |     |     |     |
                  v     v     v     v
          +--------+ +-------+ +--------+ +-----------+
          | Router | |Packer | |Veteran | | Inspector | <--- multimodal
          | Haiku  | | Opus  | |Sonnet  | |  Haiku    |      (photos)
          +--------+ +-------+ +--------+ +-----------+
              |        |          |             |
              v        v          v             v
        OR-Tools   custom    embedding     warehouse
        VRP        packer    + cosine       photos
                              over 889
                             transports

                       <-- shared LoadPlan JSON, cached -->
```

- **Dispatcher** decides which sub-agents to invoke for each user turn.
- **Router** reasons over geography + time windows and proposes / re-orders stops.
- **Packer** decides the 3D layout, justifies it, simulates what-ifs.
- **Veteran** retrieves the most similar past transport and narrates it as a
  reference: *"Today is closest to 11515121 — Fran on DR0027, same Tuesday in
  February. He started with DD13100043 then went to DD13100058. Two clients
  always take a Vichy+CC pair, place them adjacent."*
- **Inspector** analyses warehouse / truck / pallet photos and adds visual
  observations to the plan: *"The mosaic-pallet pattern in photo 20:42:35
  matches what we propose for stop 4. The barrels in photo 15:58:42 stack
  4-high in the ENVASE zone — keep them away from glass."*

Track-1 (Brain) owns Dispatcher, Router, Packer, Veteran (4 agents) +
algorithms + RAG index + backend. Track-2 (Face) owns Inspector (1 vision
agent) + the entire frontend that visualises the four other agents' streams +
photo annotation UI + voice/chat input.

Both tracks ship working AI. Both tracks see each other's outputs.

---

## Shared backbone (what crosses the wall)

### 1. Contracts ([`backend/contracts.py`](backend/contracts.py))

Pydantic schemas. `RouteRequest`, `LoadPlan`, `Stop`, `Cell`, `TimelineFrame`,
`Alert`, `Action`, `Metrics`. **Stable. Change with chat ping.**

### 2. Streaming protocol (SSE)

Backend exposes `POST /chat` and emits a stream of typed events:

```jsonl
{"type":"agent_start","agent":"dispatcher"}
{"type":"text_delta","delta":"Looking at today's route..."}
{"type":"tool_call","agent":"router","tool":"compute_route","args":{...}}
{"type":"tool_result","agent":"router","result":{...}}
{"type":"plan_patch","patch":{...}}                 // truck 3D updates
{"type":"agent_call","from":"dispatcher","to":"veteran"}
{"type":"observation","agent":"inspector","photo":"15:58:42","note":"..."}
{"type":"agent_done","agent":"dispatcher"}
```

Frontend reads it, splits by `agent`, animates accordingly. Tool calls become
inline cards in the chat. `plan_patch` events drive the 3D truck animation.

### 3. Cached load plan

The current `LoadPlan` JSON (~50 KB) is injected as a `cache_control:
ephemeral` system block in every agent call. Sub-agents read but never write
it directly — they emit `plan_patch` events the Packer applies.

### 4. Photo registry

`backend/photos.json` lists the 47 photos with timestamps, captions (we
write them), and tags (`warehouse_aisle`, `truck_loading`, `returnable_zone`,
`mosaic_pallet`, etc). Inspector and the frontend gallery both consume it.

---

## Track 1 — Brain (4 agents + algorithms + backend)

> Owns the multi-agent orchestrator, the algorithm core, the RAG index, and
> the API. If the jury asks "what is the AI doing under the hood", this track
> answers.

### Agents owned

#### Dispatcher (Sonnet 4.6)
- System prompt: "You are the experienced traffic chief at DDI Mollet. You
  coordinate Router, Packer, Veteran and Inspector to deliver a load plan
  that balances warehouse-prep cost and delivery cost (mentor's exact
  framing). You explain decisions to the user in clear, terse Spanish or
  English."
- Tools: `call_router`, `call_packer`, `call_veteran`, `call_inspector`,
  `read_plan`, `commit_plan`.
- Streams its reasoning steps to the frontend.

#### Router (Haiku 4.5)
- Proposes a stop order. Internally calls a deterministic OR-Tools VRPSPD
  heuristic (or our own greedy with park-and-walk clusters). Wraps the
  output with a one-paragraph explanation.
- Tools: `compute_route(stops, weights)`, `evaluate_route_metric(route)`,
  `find_park_and_walk_clusters(stops)`.
- Consumes the cluster teammate's input when present; falls back to its own
  clustering when not.

#### Packer (Opus 4.7)
- Strongest model — needs spatial reasoning. Decides per-stop column,
  per-pallet level, fragile-vs-heavy stacking, returnables fill-back.
- Tools: `pack_route(load_plan)`, `simulate_swap(a, b)`,
  `validate_constraint(name)`, `estimate_handling_cost(stop)`.
- Output is a `LoadPlan` patch the frontend animates.

#### Veteran (Sonnet 4.6) - the RAG one
- Indexed: 889 historical transports as feature vectors (route, driver, dow,
  zones tf-idf, SKUs tf-idf, scalars). Cosine search over numpy, no FAISS
  needed at this scale.
- Tools: `find_similar_transport(today)`, `recall_driver_pattern(driver,
  route)`, `expected_returnables_for_client(client_id)`,
  `narrate_reference_transport(id)`.
- Critical insight from research: row order in `Detalle_entrega.csv` is
  **`Entrega` order, not stop order**. 50% of transports revisit a zone.
  Aggregate at `Entrega` level when building features. Driver-route bigrams
  are the cleanest signal.

### Algorithms / data owned

- **ETL** ([`backend/etl.py`](backend/etl.py)) — fix the ordering bug
  surfaced by research. Atom of order is `Entrega`, not row.
- **Heuristic packer** ([`backend/packer.py`](backend/packer.py)) — see
  rules in `cerebro/05_fleet.md`. Cap whole-pallet stops at 4. Park-and-walk
  clusters share a column. Returnables fill freed cells.
- **Embedding index** ([`backend/veteran_index.py`](backend/veteran_index.py))
  — build per-`Transporte` vectors, save to `data/transport_index.npz`.
- **Similarity search** — numpy dot-product on 889 normalised vectors.
- **Returnables predictor** — deterministic SKU-pair lookup
  (`CJ13<->ED13`, `BRL30V<->ED30`, ...). No ML needed.
- **Driver fingerprints** — bigram zone-transition tables per
  (`Repartidor`, `Ruta`). Served to the Veteran agent as Markdown.

### Backend stack

- FastAPI + SSE for streaming.
- **Claude Agent SDK** (not the bare Anthropic SDK) for the orchestration
  loop, sub-agent spawning, automatic context compaction.
- Prompt caching: `cache_control: ephemeral` on the system prompt + LoadPlan.
  Expected 40-70% cost reduction (research finding).
- Model selection per role: Sonnet for dispatcher/veteran, Haiku for router,
  Opus for packer.

### Phases (Brain)

| Phase | T+ | Tasks |
|---|---|---|
| **B1 — Foundations** | 0-2 h | Run ETL (fix `Entrega` ordering). Verify `RouteRequest` JSON. Build `photos.json`. |
| **B2 — Veteran index** | 2-5 h | Build 889 per-transport feature vectors. Save .npz. Implement `find_similar_transport`. Test with 3 example queries. |
| **B3 — Packer + Router** | 5-9 h | Heuristic packer that emits a full `LoadPlan`. Greedy router with park-and-walk grouping. Both wrapped as agent tools. |
| **B4 — Multi-agent loop** | 9-13 h | Dispatcher with tool-use over the 4 sub-agents. SSE endpoint `/chat`. End-to-end: user prompt -> reasoning stream. |
| **B5 — Augmented albaran** | 13-15 h | HTML template for the printed sheet with `[truck slot, level]` annotations + veteran tip + per-stop alerts. `GET /albaran/{stop}`. |
| **B6 — Polish** | 15+ h | Caching tuning. 2-3 demo routes pre-warmed. Latency profiling. |

### Brain deliverables checklist
- `backend/etl.py` (fixed)
- `backend/contracts.py` (already done, frozen)
- `backend/veteran_index.py` (build + query)
- `backend/packer.py`
- `backend/router.py`
- `backend/agents/dispatcher.py`, `router.py`, `packer.py`, `veteran.py`
- `backend/main.py` (FastAPI + SSE)
- `backend/albaran.py` + Jinja template
- `backend/data/route_*.json`, `data/plan_*.json`, `data/transport_index.npz`,
  `data/photos.json`

---

## Track 2 — Face (1 agent + visual stack + interactive AI)

> Owns the Inspector agent, the entire frontend, and the interactive AI
> experience. If the jury asks "is this guapo?", this track answers.

### Agent owned

#### Inspector (Haiku 4.5, multimodal)
- Lives in the backend (Track 1 hosts the endpoint) but is **driven from the
  frontend**: the user clicks a photo or picks one in the chat, the Inspector
  is invoked with that image + the current `LoadPlan` JSON.
- System prompt: "You are an operations engineer at DDI Mollet. You look at
  warehouse and truck photos and extract concrete, actionable observations
  for the load plan. Cite specific objects (barrels, pallet stacks, dock
  positions, returnable zones) and tie each observation to a stop, a cell
  in the truck, or a layout suggestion."
- Tools: `annotate_cell(x, level, note)`, `flag_alert(severity, code,
  message, stop_order)`, `suggest_swap(a, b, reason)`,
  `update_metric(name, delta)`.
- Multimodal trick: a single Claude call gets the image AND the load plan
  AND a tool schema — it can output both an observation and a `plan_patch`
  in one inference. Confirmed by research.

The Face owner writes the Inspector prompt, the photo selector logic, and
the UI that streams its reasoning + tool calls + annotations.

### Frontend stack

- **Vite + React + TypeScript + Tailwind**, dark theme, accent `#E30613`
  (Damm red).
- **Three.js via `@react-three/fiber` + `@react-three/drei`** for the
  3D truck.
- **Leaflet + react-leaflet** for the map.
- **Vercel AI SDK** (`useChat`) to consume the SSE stream — handles tokens,
  tool calls, parallel agents out of the box.
- **Zustand** for shared state across panels.

### Panels (4)

#### A. 3D Truck (centre)
- Cargo box wireframe, scaled to truck type.
- Each `Cell` is a coloured box; colour encodes destination stop.
- Returnable cells get a striped material + small "R" billboard.
- Translucent lateral curtains that "open" at the current stop.
- **Inspector annotations** float as billboards next to specific cells:
  *"Stack matches mosaic-pallet pattern from photo 20:42:35"*. Click the
  billboard to open the photo overlay.
- Stop scrubber at the bottom with one tick per stop. Animates between
  `timeline[i]` and `timeline[i+1]`.
- 4 camera presets: top, side, rear, isometric.

#### B. Map (left)
- Leaflet basemap. Stops as numbered markers. Polyline of the route.
- Park-and-walk clusters drawn as a single shape (one drop point + walking
  arrows to the inner customers).
- Hover synced with the 3D scrubber.
- Toggle "Today vs Optimised" — overlay both routes.

#### C. Chat (right)
- Talks to `POST /chat`. Streams the multi-agent SSE.
- Each agent gets its own colour/icon. Tool calls show as inline cards
  with input/output. The user sees Dispatcher delegating to the others —
  this is the "we are not a black box" moment.
- Quick-reply chips: *"Why this order?"*, *"Compare with the most similar
  past transport"*, *"What if I swap stops 3 and 4?"*, *"Analyse the
  warehouse photo for the returnables zone"*.
- **Voice input** (stretch, easy with the browser's `MediaRecorder` +
  Whisper via the API) — the user says "swap stops 3 and 4" out loud, the
  3D animates, the Veteran chimes in.

#### D. Photos & Albaran (tab on right of 3D)
- Gallery of 47 thumbnails grouped by `warehouse / truck-loading /
  returnables / exterior`.
- Click a photo -> Inspector is invoked -> overlay shows bounding-box-style
  annotations + a panel of observations + plan patches the Inspector
  proposed.
- Subtab "Driver's sheet": embedded `iframe` of `GET /albaran/{stop}`.
  Side-by-side: original Hoja Carga PDF on the left, augmented sheet on
  the right with arrows pointing to the new info.

### Interactive AI experiences (Face's own AI surface)

These are NOT just dressing the Brain's output. They are AI that lives on
the Face side:

1. **Vision Inspector loop.** User picks a photo, frontend POSTs to
   `/inspect` (which Track-1 hosts but Track-2 designs the prompt and the
   UI). The Inspector returns annotations that the 3D scene renders as
   in-world labels. **This is multimodal AI driving 3D rendering** — that
   is the "guapo" headline.
2. **Voice -> Dispatcher.** Browser captures audio, sends to
   `/transcribe` (Whisper) -> text -> Dispatcher. Hands-free demo moment.
3. **Live what-if.** User drags a stop in the map; Face sends `simulate_swap`
   request; Dispatcher streams Router + Packer reasoning; the 3D animates
   the diff in <2s.
4. **Generative tooltip.** Hovering a cell in the 3D shows a 1-line
   AI-generated explanation: *"this is a 4-case stack of FD13 for BAR EL
   TUPÍ, matched with 4 empty CJ13 returns at unload"*. Cached on the
   Inspector side.
5. **Photo-grounded sanity check.** Before the user "approves" the plan, a
   modal shows 2-3 photos that match the proposed configuration, each with
   the Inspector's observation pinned. Visual proof the plan is feasible.

### Phases (Face)

| Phase | T+ | Tasks |
|---|---|---|
| **F1 — Skeleton** | 0-2 h | `npm create vite` inside `app/frontend`. Tailwind, R3F, Leaflet, Zustand, Vercel AI SDK. Mock data file with a sample LoadPlan + photo paths. |
| **F2 — 3D truck v1** | 2-6 h | TruckScene with cells coloured by stop, scrubber, 4 camera presets. Animation between two timeline frames. |
| **F3 — Map + KPIs** | 6-9 h | Leaflet stops + polyline. Park-and-walk cluster shape. KPI cards. |
| **F4 — Chat + agent stream** | 9-13 h | SSE consumer with per-agent colouring. Tool-call cards. Quick-reply chips. Live what-if hookup with 3D animation. |
| **F5 — Inspector + photos** | 13-17 h | Photo gallery. Click -> Inspector call. Annotations overlay on 3D + photo modal. Subtab augmented albaran preview. |
| **F6 — Voice + polish + pitch** | 17+ h | Whisper voice loop. Generative tooltip. Photo-grounded approval modal. 90-second backup recording. Slide deck. |

### Face deliverables checklist
- `frontend/` running on `:5173`, hot-reload.
- 4 panels working with the real backend.
- Inspector prompt + UI tested on at least 6 photos (2 per category).
- Voice loop demoable on the hackathon laptop's mic.
- Slide deck (6 slides).
- 90-second screen recording of the full demo (backup if Wi-Fi dies).

---

## How the two tracks correlate (the secret sauce)

This is the part that makes the whole more than the sum:

- **Same `LoadPlan`, two views.** Brain produces it. Face renders it. The
  cached JSON is the single source of truth — no duplication, no drift.
- **Same SSE stream, four agents.** Dispatcher (Brain) emits one stream that
  feeds both the chat and the 3D animation. The chat shows reasoning, the
  3D shows consequences. They move in lockstep.
- **Inspector bridges.** Inspector is a backend agent (Brain's territory)
  driven by frontend interactions (Face's territory). When the user clicks a
  photo, Face triggers a Brain endpoint that runs the Inspector and emits
  events both sides consume.
- **Veteran narration grounds the visualisation.** The most similar past
  transport (Veteran's job, Brain side) is shown in Face as an overlay map
  and an "what happened on that day" timeline. *Brain finds it, Face shows
  it.*
- **The augmented albaran ties it all.** Brain renders the sheet. Face
  embeds it. The PDF download is the artefact the driver takes home.

---

## Pitch story (for the demo)

1. **Setup (15s).** Today, a substitute driver doing Fran's route DR0027
   loses 90 minutes searching for products in the truck. (Show the real
   Hoja Carga vs Hoja Ruta from the cerebro evidence.)
2. **Veteran retrieval (30s).** "Today's route is closest to transport
   11515121 — Fran on a similar Tuesday. Here is what he did." (Veteran
   panel speaks; map overlays past route.)
3. **Plan generation (30s).** Dispatcher invokes Router + Packer. 3D truck
   fills up with colour-coded cells in route order. KPIs settle.
4. **Vision check (30s).** User clicks a photo of the warehouse. Inspector
   says "this matches the mosaic-pallet pattern; barrel zone is on the
   left side, do not stack glass on top of pallet 4". Annotation appears
   in the 3D.
5. **What-if (30s).** User says (voice) "swap stops 3 and 4". Dispatcher
   re-plans. 3D animates the diff. Veteran flags "this is closer to how
   Fran did it on 2026-02-13 — minus 14 minutes".
6. **Augmented albaran (15s).** User prints. Real paper, ready for the
   cabin.
7. **Impact + next steps (30s).** Quantitative impact slide. Roadmap to
   pilot at one Mollet route, then 32 other DDI centres.

Total: 3 minutes 0 seconds. Buffer for Q&A.

---

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Multi-agent latency too slow live | Med | Pre-warm two demo routes. Cache responses. Run one happy-path on a fallback when Wi-Fi flakes. |
| Inspector hallucinates from photos | Med | Constrain the tool schema tightly. Inspector cites the photo timestamp. Show the photo next to the observation. |
| Vector RAG misses obvious patterns | Low | 889 transports is small; the cosine match plus narrative wrapper is robust. Driver fingerprints are deterministic, not learned. |
| OR-Tools chokes on >25 stops with TW | Low | Use `guided_local_search` with 30s cap, fall back to greedy. |
| Data ordering bug (Entrega vs row) skews baseline | Already found | Fixed in B1. Use `Entrega` as atom. |
| Three.js perf degrades with 60+ cells | Low | Cells are flat boxes, GPU-cheap. Already validated by R3F demos. |
| Two of us touch the same file | Med | Strict file ownership in this doc. Ping in chat before reaching across the wall. |

---

## Timeline (synchronised)

```
T+0          Both: read this doc. Pick track. Sync on contracts.
T+0 .. T+2   B1 ETL fixed | F1 frontend skeleton + mock plan
T+2 .. T+6   B2 veteran index | F2 3D truck v1 with scrubber
T+6 .. T+10  B3 packer+router | F3 map + KPIs
T+10 .. T+13 B4 multi-agent loop | F4 chat panel + live what-if
T+13 .. T+17 B5 albaran | F5 inspector loop + photo annotations
T+17 .. T+20 Both: integration day. End-to-end demo on real data.
T+20 .. T+24 Both: polish, pitch, dry runs, recording.
T+24+        Demo + Q&A.
```

---

## Already in the repo (don't redo)

- [`backend/requirements.txt`](backend/requirements.txt) — Python deps.
- [`backend/.env.example`](backend/.env.example) — env vars.
- [`backend/contracts.py`](backend/contracts.py) — frozen schemas.
- [`backend/etl.py`](backend/etl.py) — first cut (needs the `Entrega`-order
  fix from research finding).

---

## Pick your track

Reply "Brain" or "Face". Then both of us read the other's section so we know
what we are integrating with. Contracts are the only thing we share day to
day; everything else lives inside the track owner's files.
