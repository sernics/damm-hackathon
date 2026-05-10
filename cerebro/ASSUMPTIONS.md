# Assumptions

Decisions we've made without confirmation. Each is listed with the *why* and the *risk if wrong*.

> Whenever an assumption gets confirmed (or refuted), promote it into the relevant module file (and remove the marker), and move the associated question from `QUESTIONS.md` to its "Resolved" section.

---

## A1 — The row order in `Detalle_entrega.csv` IS the historical visit order

**Reason.** In `Transporte 11515121` (32 deliveries), the `ZonaTransp` field progresses monotonically from `DD13100001` outwards (`001 → 007 → 012 → 013 → 016 → 018 → 026 → 028 → 054`), which corresponds geographically to a route radiating from Mollet → Bellavista → Granollers → Montornès → Sant Joan de les Abadesses. Same pattern observed in another two transports we sampled. The file is also internally grouped by `Entrega` (each delivery's lines are contiguous).

**Risk if wrong.** Our baseline ("today's process") wouldn't actually be today's process. We'd compare optimised metrics against a fictional baseline. Mitigation: also report metrics against a "purely geographic order" baseline.

**How to confirm.** Q3 in `QUESTIONS.md`. Ask DDI mentors directly. Or get the Trip Priority Number field from SAP for cross-check.

---

## A2 — A returnable case occupies the same physical volume as the corresponding full case

**Reason.** Same plastic crate, just empty. `CJ13` is exactly the same plastic carton as `ED13`'s outer case. `BRL30V` is the same 30 L stainless barrel that `ED30` shipped in. Photos confirm.

**Risk if wrong.** Volume calculations during the route would be off. Particularly for non-standard items (`3ENV0xxx`) where the empty might nest more compactly than the full.

**How to confirm.** Q4. Validate with mentors and / or by inspecting a few sample materials physically.

---

## A3 — Each truck loads pallets in a single floor row, but with internal partitions that fold (REFINED)

**Confirmed by mentor session 2.** Pallets sit on the floor in a single row (no pallet-on-pallet stacking). The internal partitions between pallet slots are articulated and **fold up**, so a pallet can be dragged from a middle slot to the rear with a pallet jack — provided the path is clear.

**Therefore.** The unloading model is **LIFO with reshuffle**: position k can be unloaded as a whole pallet only after positions k+1..N are empty, but mid-route any cleared slot becomes a "rear" candidate for a whole-pallet extraction.

**Cap on whole-pallet stops per route: 2-4 maximum.** Beyond that, the operation collapses into "shuffle every pallet for every stop" which is too slow. So our solver should **never propose more than 4 whole-pallet customer stops on a single route**.

**Risk if wrong.** Low — this is now mentor-confirmed.

---

## A4 — `Volumen` in ZM040 is liquid volume, not bounding-box volume

**Reason.** For SKU `0CF0054`, ZM040 says `Longitud × Ancho × Altura = 100 × 120 × 169 cm` (= 2.028 m³ bounding box) and `Volumen = 475.2 L`. 475.2 / 60 cases = 7.92 L per case. A case of 24 × 0.33 L bottles is 7.92 L net liquid. Match.

**Therefore.** For physical truck-volume planning we use **`L × A × H` from the PAL row, divided by the per-UMA `Contador`** to get cubic dm of a case / bottle / unit.

**Risk if wrong.** We'd grossly under-estimate volume.

---

## A5 — UMV codes have stable meanings

`CAJ = caja, UN = unidad, BOT = botella, BRL = barril, TB = tubo (CO₂), PAK = pack, EST = estuche, ZPR = promo, PQ = paquete, TIR = tira, BID = bidón`. No internal contradiction in the data.

**Risk if wrong.** Volume per line wrong. Low risk.

---

## A6 — Trucks have lateral access along the entire length of both sides

**Reason.** Photos clearly show fold-up tarpaulins running the full length. The presentation explicitly mentions "acceso lateral por lonas".

**Risk if wrong.** Some sections might have rigid panels (refrigeration partitions, security side, etc.). For the medium trucks visible, all sides do roll up.

---

## A7 — "Albarán prefix" maps to delivery type as 827=cash, 828=credit, 841=pure return

**Reason.** 841 lines are dominated by retornables-only and have no full products on them — strong indicator. 827 vs 828 split is plausible by analogy with industry conventions.

**Risk if wrong.** We'd wrongly categorise some flows as "returns only" when they're actually full deliveries.

---

## A8 — Mollet operates Mon–Fri only, 06:00 start, soft return cutoff (REFINED by mentor session 2)

**Reason.** Data has zero transports on Saturday and Sunday across 43 days. Mentor confirms first truck out at 06:00. Return cutoff is **soft** — varies between ~12:00 (Monday in winter) and ~19:00 (Friday in summer), demand-driven.

**Implication for the model.** Don't model a hard "return by X" deadline. Treat route duration as a soft objective only.

**Risk if wrong.** Low.

---

## A9 — All DDI clients in our data are HORECA (sector 8 = HORECA bars/restaurants)

**Reason.** The address master shows mostly bars, restaurants, hotels, cafeterias, "BAR ...", "RESTAURANT ...", "CAFETERÍA ...". `Sector = 8` is the dominant value in `Horarios`.

**Risk if wrong.** Some clients (e.g. supermarkets, gas stations) might have very different operational patterns.

---

## A10 — Almost no refrigerated cargo (but not zero — corrected)

**Original assumption (wrong).** "There is no refrigerated cargo." → **Refuted by the data audit.**

**Corrected.** A handful of SKUs do live in `Ubic. = CAMARA` in `Materiales_zubic.csv` (e.g. `0LT0021 — CACAOLAT MINIBRIK SLIM 20CL P6 24U`). The vast majority of the catalogue is ambient, but we should:
- Detect SKUs with `Ubic. = CAMARA` and tag them as cold-chain.
- Treat them as a small cluster with its own constraint (don't pack on top of heat sources, possibly stop them being on the truck for too long — though for our routing horizon of < 1 day this is probably negligible).

**Risk if wrong.** Low — even if we mis-tag, the cardinality of cold SKUs is tiny.

---

## A11 — A driver runs 1–2 transports per day (DOUBLE-CORRECTED, mentor-confirmed)

**Original assumption (wrong).** "The truck makes one trip per day." → Refuted by raw data.

**Data-only correction (also wrong-ish).** Saw up to 9 (date, driver) pairs in the file and concluded "30 % of drivers run multiple transports per day, max 9".

**Mentor-confirmed truth (2026-05-09).** A driver does **1–2 transports per day**, with 9–20 customers per transport. If they do two, they reload the same truck. The 3+ transports we saw in the data are edge cases — likely abonos / pure-return albaranes (`841...` prefix) showing up as separate "transports" in the file, or data noise. We should re-investigate the 1 (date, driver) pair with 9 transports — almost certainly it is mixed `841` / cancelled / re-issued documents inflating the count.

Distribution of (date, driver) -> transports per day in raw data (kept here for honesty):

| transports/day | pairs |
|---:|---:|
| 1 | 474 (70 %) |
| 2 | 133 (20 %) |
| 3 | 28 |
| 4–9 | 9 |

Reading: 90 % of pairs match the mentor's "1–2 transports/day" rule. The remaining 10 % is the bucket we should investigate before drawing conclusions.

**Implication.** Our routing horizon is per transport. We do not model driver fatigue or sequencing within a day. Truck reuse on the second transport of the day is a separate, smaller question (does that change the truck's usable capacity for transport 2 if it still has unprocessed empties from transport 1? — probably not, since drivers offload empties at base between trips).

---

## A12 — Picking starts before the truck leaves; "modify before liquidation" = our recommendation must be ready before picking begins

**Reason.** SAP rule explicitly stated. The picker uses the Hoja Carga which is generated at the start of the loading window.

**Risk if wrong.** Our system could be adopted at a different point in the workflow with different latency requirements.

---

## A13 — Default time window for clients without horario data is 08:00–22:00 weekdays

**Reason.** HORECA convention: most bars/restaurants are open 08:00–02:00, but deliveries usually 08:00–13:00 + 17:00–22:00. We'll use the wider window unless told otherwise.

**Risk if wrong.** Some restaurants only accept morning or only evening deliveries. Note coverage is **only ~10 %** of active clients (120 / 1.203), so this default applies to ~90 % of stops.

---

## A14 — In `Detalle_entrega`, multiple lines for the same `(Entrega, Material, UMV)` should be summed

**Reason.** We see ~9.500 rows where the same (Entrega, Material) appears 2+ times with positive quantities — likely batch / lot / promotion splits in SAP. For volume planning, the customer ultimately receives the **sum** of these lines.

**Risk if wrong.** Low — if there's a reason these stay split (e.g. different price levels are physically segregated), our space estimate is unchanged anyway.

---

## A16 — Weight (kg) is not a binding constraint; the model operates in cases (CONFIRMED)

**Mentor session 2.** "El peso no lo hagáis caso. Hagáis caso a las cajas."

**Implication.** Drop kg as a constraint or penalty. The hard physical limit is **case count and pallet count**, not mass.

**Risk if wrong.** Low — the mentor is explicit.

---

## A17 — Driver-truck pairing is stable input, not a decision variable (CONFIRMED)

**Mentor session 2.** "El repartidor nunca cambia de camión. Siempre tienes tu camión."

**Implication.** Our solver does not search across (driver, truck) permutations. The pair is given. The decision is which clients go on each existing pair.

**Risk if wrong.** Low — the mentor is explicit.

---

## A18 — Driver license category constrains truck assignment (NEW HARD CONSTRAINT)

**Mentor session 2.** Drivers have a license-category field (level 1 / 2 / 3, exact values to confirm) in the SAP driver master. Level 1 can drive small trucks only; level 3 can drive any.

**Implication.** Our truck-to-driver assignment cannot freely permute. License compatibility is a hard constraint.

**How to confirm.** Q43 / Q44 in `QUESTIONS.md` — get the field as a column.

---

## A19 — "Cases on top of barrels" is a soft penalty, not a hard prohibition (CONFIRMED)

**Mentor session 2.** "Las cajas las pueden poner sobre los barriles. No es lo más óptimo, pero se pueden llegar a poner."

**Implication.** Our packer treats this configuration as a penalised state, not a forbidden one. Same logic likely applies to other "preferred but not required" stacking rules.

---

## A20 — Customer cluster pattern: "park once, walk to N nearby clients" (NEW)

**Mentor session 2.** For tight clusters, the driver parks once, walks to each client in the cluster, leaves empties on the street, and collects all empties at the end of the cluster. A pure VRP/TSP cost model treats each client as a separate truck stop and overestimates cost.

**Implication.** Our routing model should detect tight clusters (low Euclidean distance, shared `ZonaTransp`) and treat them as a single "super-stop" with internal customer visits.

---

## A15 — `Ruta` in `Detalle_entrega` is the *operating* route on that day, not the client's home route

**Reason.** Each client has a single home zone, each zone has a single home route, but 873 / 1.203 clients show up in multiple `Ruta` codes across the period. That can only be reconciled if `Ruta` reflects what actually carried that delivery, not the formal assignment.

**Risk if wrong.** Medium — if `Ruta` were actually the formal assignment, then ZONAS.csv has 1:N mappings we missed and our planning unit (the Ruta) is fluid. Either way we model individual transports, so our solver doesn't depend on this assumption — but our "compare against today's route" baseline would.

→ Tracked as Q11.

---

## How to use this list

When you read another module file and see `(assumption Ann)` next to a statement, the explanation is here. When you make a decision based on these assumptions, **explicitly note which one** in your code/document so that, if the assumption changes, downstream effects are easy to find.
