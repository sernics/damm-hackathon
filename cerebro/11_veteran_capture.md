# 11 - Veteran Capture System (audio -> Markdown -> RAG)

The component that solves "Tier B veteran knowledge" by actively soliciting it from real DDI drivers. Output is a structured Markdown knowledge base that the briefing LLM (Person B) consumes via RAG.

---

## Why this exists

The briefing LLM (Person B's component, see `08_solution_sketch.md`) needs tacit operational knowledge per client ("park at the back", "Pedro opens the side door if you call", "narrow alley, take it slow"). This information lives only in veteran drivers' heads. We don't have it in SAP, in CSVs, or on Google Maps.

This module **captures it**. The mentor in session 2 said it himself: *"Imagine I became a truck driver, I wouldn't know."* That's the gap.

---

## End-to-end flow

```
+--------+   +-----------+   +---------+   +-------+   +--------------+   +----------+
|  Cron  |-->| Selection |-->| Message |-->| Audio |-->| STT + LLM    |-->| Markdown |
| trigger|   | algorithm |   | to driver|  | record|   | extraction   |   | per-client|
+--------+   +-----------+   +---------+   +-------+   +--------------+   +----------+
                                                                                |
                                                                                v
                                                                          +-----------+
                                                                          |   RAG     |
                                                                          | (Person B)|
                                                                          +-----------+
```

Five components, each detailed below.

---

## Component 1: Cron + Selection algorithm

A scheduled job that decides **which (customer, driver) pair** to query each cycle. Not random.

### Selection priority score per (client_id, driver_id)

```
priority(client, driver) =
    w_value * client_value           (volume + frequency)
  * w_gap   * note_gap_score(client) (1.0 if no notes, 0.0 if 5+ recent)
  * w_freshness * staleness(client)  (1.0 if no recent updates, decays)
  * w_familiarity * delivered_count(driver, client) (more = better testimony)
  * w_volume * pending_volume(client)  (priority if today's load is big)
```

### Practical rules

- Queue a maximum of **3 (client, driver) prompts per driver per week**. Drivers will ignore us if we spam.
- Prioritise:
  1. **High-volume clients with no notes yet** (biggest impact).
  2. **Tricky clients** (long historical unload time if we have it, frequent stockouts/retries).
  3. **Clients new in this period** that don't have any notes.
  4. **Clients with stale notes** (> 6 months).
- Use `Detalle_entrega.csv` to find which drivers have most experience with which clients (count of past deliveries) -> only query drivers who actually know the client.

### Scheduling

- Send messages between **18:00 and 20:00** (driver finished route, more relaxed, before dinner).
- Do not message on Saturdays / Sundays.
- One message at a time. Don't queue 5 at once.

---

## Component 2: The message to the driver (the prompt design)

The wording matters. Vague prompts get vague answers. The driver gets a short, specific message — ideally on **Telegram or WhatsApp** (they have it on their phone, no app to install).

### Template

```
Hola Fran! Eres uno de los conductores que más cubre BAR EL TUPÍ
(Carrer Major 23, Sant Julià de Vilatorta).

Si tienes 30 segundos, grábanos un audio respondiendo a estas 3 cosas
(no hace falta orden, dilo como te salga):

1. Donde aparcas / como entras al cliente
2. Si hay alguien especifico que te atiende (nombre, horario)
3. Algun truco operativo (por donde subes barriles, donde dejas vacios,
   alguna cosa rara del cliente)

Si no tienes nada que decir o ya lo grabaste, ignoralo y a otra cosa.
```

### Why this prompt design works

- **3 specific questions** > "cuentame del cliente". Veterans answer concrete questions easily.
- **30-second framing** lowers commitment.
- **Permission to ignore** removes guilt -> better long-term participation.
- **Use the actual customer name and address** -> driver visualises immediately.
- **Mention "uno de los que mas cubre"** -> appeals to expertise / pride.

### Variants per situation

- **First-time client never queried**: emphasise "no tenemos info de este cliente".
- **Stale notes**: "lo que sabiamos era de hace X meses, esta todo igual?".
- **Conflicting notes**: "otro conductor dijo X, tu lo confirmas o no?".
- **Big-volume day tomorrow**: "manana llevas un pedido grande para este cliente, algo que el de cubrir tenga que saber?".

---

## Component 3: Audio capture and storage

### UX — channel choice

We do NOT know what messaging app DDI drivers use. The mentor only confirmed they use the printed albarán as their work interface and "no GPS apps". So the channel is an open assumption.

Realistic ranking for Spain:

1. **WhatsApp Business API** (production-realistic): ~95 % smartphone penetration in Spain, drivers already have it. Native voice messages. Requires DDI to onboard as a WhatsApp Business sender (Twilio / Meta direct / 360dialog). Best for the real product.

2. **Webapp + SMS link** (hackathon-realistic): a dead-simple page (Streamlit / FastAPI + HTML), with one big microphone button. Link delivered via SMS or any chat. Zero install. Browser handles audio recording natively. **This is what we should build for the hackathon demo** — fastest to ship, works on any phone.

3. **Telegram Bot**: best Bot API of the three but minority adoption in Spain outside of technical niches. Forces drivers to install. Reasonable as a fallback if WhatsApp is too slow to onboard.

Coordinate with the mentor: ask which channel DDI would actually deploy. Could resolve with one line: "WhatsApp serviria?" or "los repartidores tienen Telegram?".

### Tech

- Audio file: any format (`.ogg` from Telegram, `.m4a` from web). 16 kHz mono is plenty.
- Max duration: **2 minutes** (cap it; longer audios suggest the driver got distracted).
- Storage: local while processing, **deleted after transcription**. Only the transcript is kept (privacy).

### Consent

- First message to each driver includes: *"Tus audios se transcriben automáticamente y se borran. Solo guardamos el texto. Tu nombre aparece como autor del consejo. Puedes pedirnos borrar tus aportaciones cuando quieras."*
- Track per-driver opt-in/out flag.

---

## Component 4: STT + LLM extraction

### Pipeline

1. **Speech-to-text**: Whisper (large-v3 or via OpenAI API). Handles Catalan/Spanish mix natively. Robust to ambient noise (driver might record from cab).
2. **LLM extraction**: pass the transcript + the customer context to an LLM (Claude or GPT-4o) with a strict system prompt:

```
Eres un sistema que extrae tips operativos de transcripciones de
conductores. Tu output debe ser SOLO un JSON con esta estructura:

{
  "client_id": "9100696143",
  "driver_id": "850004",
  "captured_at": "2026-05-15T19:23:00",
  "tips": [
    {
      "topic": "parking | access | contact_person | barrels | empties | hours | warnings | other",
      "text": "<frase corta, 1-2 lineas, en castellano>",
      "confidence": "high | medium | low"
    }
  ],
  "raw_transcript": "<la transcripcion completa, para auditoria>"
}

Reglas:
- No inventes nada. Si la transcripcion no menciona X, no escribas X.
- "confidence high" solo si el conductor lo dice de forma rotunda.
- Si la transcripcion es ininteligible o vacia, devuelve "tips": [].
- Si detectas opiniones inapropiadas / ofensivas hacia el cliente,
  marca el tip con "topic": "other" y "confidence": "low" - se
  filtran aguas abajo.
```

### Moderation

- Auto-filter: an LLM second pass that checks for inappropriate content before writing to Markdown. Tips with `topic="other"` AND `confidence="low"` get held for manual review.
- Don't let the system propagate "Pedro is an idiot" tier content.

---

## Component 5: Markdown knowledge base (the RAG source)

### File layout

One file per client, in `dataset/veteran_notes/{client_id}.md`:

```
+- dataset/
   +- veteran_notes/
      +- 9100696143.md
      +- 9100627695.md
      +- ...
      +- _index.md          (table of contents, refreshed each write)
      +- _gaps.md           (clients with no notes yet, refreshed)
```

### Per-client schema

```markdown
# Cliente 9100696143 - LOS TERESITOS

## Quick facts (auto-generated from data, not from drivers)
- Address: Carrer Llevant 2, 08110 MONTCADA I REIXAC
- Zone: DD13100043 - MONTCADA I REIXAC
- Typical visit volume: 8 cases (median over 12 deliveries)
- Frequency: weekly, usually Wednesdays
- Returnable rate: 96 %

## Access (from public sources)
- Google: bar at street level, calle ancha, parking visible in front
- Streetview: glass facade, no steps, side alley to the right

## Veteran tips

### Parking
- [850004 Fran Romero, 2026-05-12] "Aparca en la plaza de enfrente, no enfrente del bar. La acera es estrecha." `[high confidence]`
- [855203 Jacint Mas, 2026-04-20] "Hay carga y descarga 8-11h, despues complicado." `[high confidence]`

### Access / contact
- [850004 Fran Romero, 2026-05-12] "Si llegas antes de las 9, llama a Pedro al telefono que viene en el albaran. El te abre la lateral." `[medium confidence]`

### Barrels / heavy items
- (no notes yet)

### Empties / returnables
- [855203 Jacint Mas, 2026-04-20] "Dejan los cascos apilados en la entrada lateral, fenomenal." `[high confidence]`

### Warnings
- (none)

## Last updated: 2026-05-12
## Number of veteran inputs: 2
## Multi-driver consensus: 0 (each tip from a different driver, no overlapping confirmation yet)
```

### Why this schema

- **`Quick facts` and `Access` come from data + web** (not driver). Always there even on day 1.
- **`Veteran tips` are sectioned by topic** so RAG retrieval can be filtered.
- **Provenance** (`[driver_id name, date]`) on every tip -> traceable, no hallucination claim possible.
- **Confidence label** -> Person B's briefing LLM can weight or filter.

### Index file

`_index.md` is regenerated on every write:

```markdown
# Veteran notes index (auto-generated 2026-05-15)

| Client | Notes | Last updated | Coverage |
|---|---:|---|---|
| 9100696143 LOS TERESITOS | 3 | 2026-05-12 | parking, access, empties |
| 9100627695 BAR PAVELLO | 0 | - | (gap) |
| ... |
```

### Gaps file

`_gaps.md`:

```markdown
# Clients without veteran notes (priority list for cron)
- 9100627695 BAR PAVELLO ST JULIA - 18 historical deliveries, 0 notes
- 9100755605 BAR L'ARPA - 12 historical deliveries, 0 notes
- ... (sorted by historical volume)
```

This file feeds back into Component 1's selection algorithm.

---

## Multi-driver consensus aggregation

When 2+ drivers say the same thing about a client, that's high-signal. The system should detect this:

```python
# Pseudocode
def aggregate_tips(client_id):
    tips = load_all_tips(client_id)
    grouped = group_by_topic(tips)
    for topic, items in grouped:
        if len(set(t.driver_id for t in items)) >= 2:
            # 2+ different drivers -> mark as confirmed
            mark_consensus(items, level="confirmed")
        if any conflicting tips on same topic:
            flag_for_review(items)
```

Display in Markdown:

```
### Parking
- [CONSENSUS - 3 drivers] Aparca en la plaza de enfrente.
  - 850004 Fran Romero, 2026-05-12
  - 855203 Jacint Mas, 2026-04-20
  - 850018 Ruben Diaz, 2026-03-30
```

This is gold for the briefing LLM — high-confidence single-line input.

---

## Coordination with Person B (briefing LLM)

Person B's component reads the per-client Markdown to enrich the briefing. Things to align with Person B BEFORE building:

- **Format of the markdown they expect** (the schema above is a proposal — confirm).
- **RAG strategy**: full-file retrieval per client (simple, fits in context) vs. chunked vector store. Probably full-file is fine — there are 1.203 files but per-route only 18 are needed at a time.
- **Citation format in their briefing output** — should the briefing say "según Fran, ..." or just embed the tip?
- **Conflict resolution**: when 2 tips conflict, what does Person B's briefing do? Show both? Show the high-confidence one only?

Schedule a 30-min sync with Person B on day 1 of the build.

---

## Coordination with Person A (clusters + truck filling)

Person A's output (clusters, truck-fill plan) plus this Markdown both feed Person B. Three artifacts go into the briefing prompt:

1. Today's planned route + load (Person A).
2. Per-client veteran notes Markdown (this component).
3. Public data (Google Places, Streetview) — populated by us.

The integration point is **Person B**, who orchestrates all three.

---

## Privacy and ethics

- Driver consent is mandatory. Opt-in only.
- Audio is transient (deleted after transcription). Only text is kept.
- Driver can request deletion of their contributions at any time.
- The system is for operational improvement, not surveillance. Frame it that way to drivers.
- Do NOT send messages outside working hours (18:00-20:00 window respected).
- Do NOT use captured tips for any disciplinary or evaluation purpose.

---

## Risks

- **Driver fatigue**: if we spam, they ignore. Mitigation: max 3/week per driver, opt-out friendly.
- **Inappropriate content**: Mitigation: LLM moderation pass + manual review queue.
- **Bilingual / dialect noise**: Mitigation: Whisper handles Catalan-Spanish mix. Test early.
- **Conflicting tips**: Mitigation: aggregator flags conflicts for review.
- **Stale tips becoming wrong**: Mitigation: freshness scoring, staleness > 6 months prompts re-validation.
- **Cold start**: We start with zero notes. Mitigation: seed Day 1 with 10-20 notes from a 30-min interview with the mentor or a real driver (see `BLOCKERS_es.md`).

---

## Stretch features (for the pitch, not for v1)

- **Auto-suggest tip from data**: when frequency-of-failure or long unload time appears in data, the system pre-populates a hypothesis tip and asks the driver to confirm/deny ("creemos que aparcar aqui es complicado, lo confirmas?").
- **Photo capture along with audio**: driver snaps a photo of the parking spot, attached to the tip.
- **Client-side feedback loop**: warehouse staff can also add notes ("este pedido tiene productos especiales, llevad cuidado").
- **Tip "expiry": drivers can tap a notification "esto ya no es asi" and the system marks tips obsolete.**
- **Heatmap / dashboard for management**: which clients are best/worst documented, where the gaps are.

---

## Build plan (~12-16 hours of work for one person)

| Block | Work | Hours |
|---|---|---:|
| 1 | Set up Telegram bot + driver opt-in flow | 2 |
| 2 | Cron + selection algorithm (priority score + queue) | 3 |
| 3 | Message templates (4 variants) | 1 |
| 4 | Audio capture, storage, deletion policy | 1 |
| 5 | Whisper STT integration | 1 |
| 6 | LLM extraction prompt + JSON parsing | 2 |
| 7 | Markdown schema + writer (per-client + index + gaps) | 3 |
| 8 | Multi-driver consensus aggregator | 1 |
| 9 | Coordination layer with Person B (RAG-ready output) | 1 |
| 10 | Demo seed data (~10-20 mock veteran tips for the pitch) | 1 |
| **Total** | | **~16h** |

---

## Open questions for this module

- What language for the markdown? Spanish to match operations? Or Catalan? -> probably Spanish.
- Where does the Markdown live? Inside the repo (versioned)? Or a separate datastore? -> repo for the demo, externalised in production.
- Who has access to view tips? Drivers themselves? Just management? -> probably drivers can see the consensus on the briefing, not raw tips.
- How do we handle drivers who disagree publicly? -> conflict review queue, but the data itself stays.
