# Cerebro — Damm Smart Truck

Knowledge base for the Interhack BCN 2026 hackathon project (challenge by Damm / DDI).

All relevant information has been extracted from the source materials (CSVs, PDFs, PPTXs, photos) and organised here in Markdown so any agent (human or AI) can reason about it without re-reading the raw files.

> **Last updated:** 2026-05-09.

---

## File index

| File | Purpose |
|------|---------|
| [`00_brief.md`](00_brief.md) | Official challenge brief (English, canonical version) |
| [`01_context.md`](01_context.md) | Executive summary: the problem, the central conflict, what they want and don't want |
| [`02_data_model.md`](02_data_model.md) | Code system (DR / DD / V2 / 85 / 91 / Transporte / Entrega), SAP fields, transport lifecycle |
| [`03_data_inventory.md`](03_data_inventory.md) | All CSVs, PDFs, photos available, with row counts, column maps and key numbers |
| [`04_warehouse.md`](04_warehouse.md) | Mollet warehouse layout, location codes, loading docks, special zones |
| [`05_fleet.md`](05_fleet.md) | Truck types, capacities, lateral access, what we know and what we assume |
| [`06_returnables.md`](06_returnables.md) | The reverse-logistics flow that defines this challenge (CJ <-> ED 1:1, 60 % retornables) |
| [`07_evidence.md`](07_evidence.md) | Documentary proof of the route<->load decoupling (Hoja Carga vs Hoja Ruta) + photo notes |
| [`08_solution_sketch.md`](08_solution_sketch.md) | Architecture draft: ETL -> routing -> packing -> visualisation |
| [`09_data_quality.md`](09_data_quality.md) | **Read before any ETL.** Traps, quirks, dedupe rules, accent issues |
| [`10_mentor_session_2.md`](10_mentor_session_2.md) | Findings from the second mentor session — joint objective, partitions, license categories, park-and-walk pattern |
| [`11_veteran_capture.md`](11_veteran_capture.md) | Spec for the audio-to-Markdown veteran-knowledge capture system that feeds the briefing LLM via RAG |
| [`GLOSSARY.md`](GLOSSARY.md) | Every code and abbreviation we ran into |
| [`ASSUMPTIONS.md`](ASSUMPTIONS.md) | Every assumption we made when no source confirmed it, in one place |
| [`QUESTIONS.md`](QUESTIONS.md) | Open questions — `[BLOCKER]` / `[IMPORTANT]` / `[NICE]` |

---

## How to use it

- **Quick onboarding for a new collaborator (or AI agent):** read `00_brief.md` -> `01_context.md` -> `GLOSSARY.md`. That's enough to talk sense.
- **Before writing code:** read `02_data_model.md`, `03_data_inventory.md`, and `09_data_quality.md` (the traps section is non-negotiable).
- **Before deciding routing strategy:** read `07_evidence.md` (you'll see why the obvious answers don't apply).
- **Before deciding packing strategy:** read `05_fleet.md` and `06_returnables.md`.
- **Before launching multi-agent research:** open `QUESTIONS.md` and `ASSUMPTIONS.md` — they tell you which premises to push hardest on.

When new information arrives (a mentor answers, a CSV gets added, the jury clarifies a rule):
1. Update the relevant module file.
2. Move the answered question from `QUESTIONS.md` to its "Resolved" section with the answer.
3. Promote any unconfirmed assumption that gets confirmed into the body text and remove its marker.

---

## What is not here yet (and why)

- **Geocoded coordinates for the 1.203 clients.** Pending. Will live in the dataset folder, not here.
- **Vehicle-to-route mapping.** We don't have a clear master in the data. Tracked as Q2.
- **Truck internal dimensions.** Tracked as Q1.
- **Picking time benchmarks.** Tracked as Q6.

When any of these is resolved, this README gets a one-liner pointing to the relevant module.
