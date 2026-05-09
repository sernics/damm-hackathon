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

## A3 — Each truck loads pallets in a single floor row (no palletised stacking)

**Reason.** Photos show flatbed trucks with closed boxes. Pallets sit on the floor; cases are loaded loose on top of pallets but pallets don't stack on pallets.

**Risk if wrong.** Capacity is roughly twice what we modelled. Routes we declared "infeasible by volume" would actually be feasible.

**How to confirm.** Q1 (truck dimensions). Direct observation in Mollet.

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

## A8 — Mollet operates Mon–Fri only

**Reason.** Data has zero transports on Saturday and Sunday across 43 days.

**Risk if wrong.** A weekend route would not be modelled.

---

## A9 — All DDI clients in our data are HORECA (sector 8 = HORECA bars/restaurants)

**Reason.** The address master shows mostly bars, restaurants, hotels, cafeterias, "BAR ...", "RESTAURANT ...", "CAFETERÍA ...". `Sector = 8` is the dominant value in `Horarios`.

**Risk if wrong.** Some clients (e.g. supermarkets, gas stations) might have very different operational patterns.

---

## A10 — There is no refrigerated cargo

**Reason.** No SKU in our data suggests refrigeration. All beverages are ambient-stable, all food items are dry/canned/preserved.

**Risk if wrong.** Some refrigerated SKU we missed would impose temperature constraints on packing.

---

## A11 — The truck makes one trip per day

**Reason.** Each `Transporte` is associated with a single `FECHA`. We don't see the same vehicle making multiple `Transportes` on the same day in the limited driver-vehicle mapping we have.

**Risk if wrong.** Some routes might be split into morning + afternoon trips. Our routing horizon would be off.

---

## A12 — Picking starts before the truck leaves; "modify before liquidation" = our recommendation must be ready before picking begins

**Reason.** SAP rule explicitly stated. The picker uses the Hoja Carga which is generated at the start of the loading window.

**Risk if wrong.** Our system could be adopted at a different point in the workflow with different latency requirements.

---

## A13 — Default time window for clients without horario data is 08:00–22:00 weekdays

**Reason.** HORECA convention: most bars/restaurants are open 08:00–02:00, but deliveries usually 08:00–13:00 + 17:00–22:00. We'll use the wider window unless told otherwise.

**Risk if wrong.** Some restaurants only accept morning or only evening deliveries.

---

## How to use this list

When you read another module file and see `🟡 (assumption)` next to a statement, the explanation is here. When you make a decision based on these assumptions, **explicitly note which one** in your code/document so that, if the assumption changes, downstream effects are easy to find.
