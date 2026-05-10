# veteran-capture — overview

A 5-minute explainer of what this module does, why it exists, and how
the pieces fit together. For the code-level walkthrough see
[ARCHITECTURE.md](ARCHITECTURE.md). For build commands see
[../README.md](../README.md).

---

## The problem

Damm's distribution arm (DDI) delivers to ~1.200 active clients a week
across Catalonia. The tacit operational knowledge — *"at this client
park behind, ask for Marta, the side door is the only one wide enough
for a barrel"* — lives only in the heads of the veteran drivers who
have been doing the route for 10+ years. When one retires, that
knowledge disappears. SAP does not capture it, the printed delivery
note does not capture it, and a new driver has to relearn it
client by client by trial and error.

This module **actively captures that knowledge** before it walks out
the door, structures it, and feeds it to the briefing LLM that prints
it next to the delivery note for the next driver.

---

## The whole flow in one paragraph

A cron picks the most valuable `(client, driver)` pair to ask next.
The driver gets a link on their phone with three micro-questions about
that client. They tap a big red button, talk for 30 seconds, hit send.
Whisper transcribes the audio. Claude Sonnet extracts a list of
structured tips (parking, contact person, hours, access...). Claude
Haiku redacts personal data (phone numbers, surnames) and flags
inappropriate content. The tips land in a per-client markdown file
that the briefing LLM (Person B's module) ingests as RAG. The audio
is deleted. The next morning the driver who is about to deliver to
that client gets the tips printed on their albaran.

---

## The five pieces

```
+------------+     +-----------+     +-----------+     +-----------+     +-----------+
|  MINING    | --> | SELECTION | --> |  CAPTURE  | --> |EXTRACTION | --> |  WRITER   |
| (offline)  |     |  (queue)  |     |  (web)    |     |  (LLMs)   |     |  (RAG)    |
+------------+     +-----------+     +-----------+     +-----------+     +-----------+
```

1. **Mining** reads the raw CSVs (Detalle, Direcciones, Horarios,
   Cabecera) and produces per-client and per-driver-pair profiles. One
   row per client with: volume, frequency, retornable share, top SKUs,
   address, zone, drivers ever seen. One row per (driver, client) pair
   with delivery counts.
2. **Selection** scores every (client, driver) pair on six factors
   (volume, gap, staleness, familiarity, recency, complexity) and ranks
   them. The top of the queue is the cron's todo list.
3. **Capture** is a tiny FastAPI app with one mic button. Driver opens
   `/capture/{client}/{driver}` on their phone, records 30 s, posts.
   No login, no app to install — just a URL.
4. **Extraction + moderation** is two Claude calls. Sonnet does the
   structured extraction with tool-use (forced JSON schema, no
   hallucination). Haiku does a cheap moderation pass that redacts PII
   in place rather than rejecting the whole tip — the priority is
   preserving operational value.
5. **Writer** aggregates capture JSONs into per-client markdown files
   and a single manifest that lists every active client in
   importance order with status (filled / empty), suggested next
   driver, and link to the per-client tips.

---

## A real example: MESON 20 P KA

This is a real client in our dataset. Walk through the whole loop:

1. **Mining** sees in `Detalle.csv`: client `9100698329` (MESON 20 P KA
   in Lliçà de Vall, zone DD13100033), 27 deliveries in the period,
   1.122 cases total, 20% retornable, top SKUs `CJ13`, `0AG0007`,
   `3ENV1281`, drivers seen: `850012`, `850014`.
2. **Selection** ranks it as the day-1 #1 priority for empty clients
   because: volume is moderate-high, no tips yet (gap = 1.0), driver
   `850014` (LLUIS CORS BOIX) has high familiarity. Score: 0.883.
3. **Capture**: cron sends LLUIS the link
   `/capture/9100698329/850014`. He opens it during a coffee break,
   sees a card "Hola LLUIS — three micro-questions about MESON 20 P KA
   in Lliçà de Vall," taps record, says: *"aparcar detrás en la plaza
   del ayuntamiento, la calle principal es muy estrecha, te recibe
   Jordi (dueño) o su mujer Monse, no llegues antes de las 10..."*,
   hits send.
4. **STT**: Whisper transcribes verbatim in Spanish/Catalan mix.
5. **Extraction**: Claude Sonnet returns 5 structured tips — parking,
   contact_person, hours, access, empties — each with a confidence
   tag.
6. **Moderation**: Claude Haiku reads the tips. Finds no phone
   numbers, no surnames with full names, nothing to redact. Returns
   all 5 in `accepted`.
7. **Writer**: regenerates [`9100698329.md`](../../dataset/veteran_notes/9100698329.md)
   with the tips bucketed by topic, attributed to LLUIS, dated. The
   manifest now shows MESON 20 P KA as `filled` (priority drops, but
   importance stays — it does not disappear from the top).
8. **Briefing LLM** (Person B): tomorrow when a less experienced
   driver is assigned this client, the briefing LLM reads
   `9100698329.md`, extracts the relevant tips, and prints them on
   the albaran. The new driver knows about the side door before they
   arrive.

The whole loop takes ~30 seconds of LLUIS's time and produces a tip
that gets reused on every future delivery to MESON 20 P KA forever.

---

## The two ranking signals

Every client carries **two** scores in the manifest. They answer
different questions:

| Signal | What it measures | Stable? |
|---|---|---|
| **Importance** | How much value a tip about this client would create. Volume + retornable complexity. | Yes — only changes if the client's profile changes. |
| **Priority** | How urgent it is to ask *now*. Gap (do we have tips already?), staleness (are they old?), driver familiarity, recency of last delivery, etc. | No — drops when filled, rises when stale. |

The dashboard sorts by **importance** so a client does not collapse
in the ranking the moment it gets filled. The cron uses **priority**
inside each importance tier to pick *"of the big clients we still
know nothing about, which one is most urgent?"*.

---

## What the operator sees

A single dashboard at `http://localhost:8001/dashboard`:

- **Stats**: total clients, filled / empty, last update.
- **Filter pills**: All / Empty / Filled.
- **Search**: free text against name, ID, zone, driver.
- **Table** (20 / page): rank, client, status, tip count, suggested
  driver (with delivery count and a "limited history" warning when
  the driver only knows the client from one or two trips), importance
  and priority scores, and per-row actions:
  - **Open capture** — opens the recording page for the suggested
    driver.
  - **Copy link** — copies the URL for sending via WhatsApp, SMS,
    Slack.
  - **View tips** (filled only) — expands the row to show all tips
    inline with provenance.
  - **Open MD** (filled only) — opens the per-client markdown that
    the briefing LLM ingests.

There is also a `/api/manifest` JSON endpoint for the dashboard's
Refresh button and any future programmatic consumer.

---

## What we hand off to Person B

The contract with the briefing LLM (Person B's module) is **the
markdown files in `dataset/veteran_notes/`**. Specifically:

- `<client_id>.md` — one per client with at least one captured tip.
  Quick facts auto-generated from delivery data, plus tips bucketed
  by topic, attributed to a driver, dated, with a confidence tag and
  a consensus badge when two or more drivers agree on a topic.
- `_manifest.md` — human-readable index over every active client.
- `manifest.json` — same data plus the full tip content for filled
  clients, machine-readable.

Person B's RAG can either ingest the per-client markdown files
directly (preferred — natural format for an LLM) or query
`manifest.json` for a single-shot lookup keyed by `client_id`.

---

## What we deliberately do not do

- **No login, no driver app**. A URL on the phone is enough. Adding
  more friction kills participation in production.
- **No audio storage**. The audio file is buffered to disk for
  Whisper, then deleted. Only the transcript and structured tips
  survive.
- **No free-form text in the KB**. Tools-use forces the model to
  emit a strict JSON schema. No free-text section that could leak
  hallucinated content into the briefing.
- **No "tip database"**. The output is plain markdown. Person B's RAG
  reads files, version control sees diffs, humans grep. A database
  is the right answer in production but adds zero value at hackathon
  scale (1.203 clients, ~3 MB total).

---

## Privacy and moderation in plain terms

- **Names of pila are operational, not PII**: `"the owner is Jordi"`
  is a tip we want to keep, not redact.
- **Surnames + first name are PII**: `"Marta Lopez Ruiz"` becomes
  `"Marta"`.
- **Phone numbers, emails, DNIs**: always redacted as `[telefono]`,
  `[email]`, `[DNI]`.
- **Insults, opinions without operational value**: rejected outright.
- **If the moderation API call itself fails**: fail-open with all
  tips in `rejected`. Better to lose a capture than silently publish
  unmoderated content.

---

## What's next (out of scope today, in scope for production)

- Migrate from parquet/markdown files to SQLite locally and Postgres
  in production. The domain layer (`mining/`, `selection.py`,
  `writer/aggregate.py`) does not change — only the I/O wrapper.
- Real driver channel (WhatsApp Business or SMS) instead of a webapp
  link. Same backend, different transport.
- Multi-tenant access control (per-warehouse, per-region).
- Auto-cron on a real scheduler instead of manual `cli select`.
- Track tip *consumption* (was this tip actually rendered on a real
  albaran?) so the LLM can downweight tips that never get used.
- Re-process old captures when prompts change. The capture JSONs are
  append-only and immutable on purpose — we can re-extract and
  re-moderate any time without re-asking the driver.

---

## TL;DR for the pitch

> *"DDI loses operational knowledge every time a veteran retires.
> SAP does not capture it. The printed albaran does not capture it.
> Our system does — actively, daily, by asking the right driver about
> the right client at the right time. In 12 months you will have a
> structured knowledge base of 1.203 client-specific operational
> tips that today does not exist anywhere, in any format, at DDI."*
