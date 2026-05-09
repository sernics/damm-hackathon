# Open Questions

Living list. **Status legend:** `[BLOCKER]` (we cannot model the problem well without it) / `[IMPORTANT]` (affects the quality of the solution) / `[NICE]` (would help, not strictly needed). When a question gets resolved, move it to the "Resolved" section below with the answer.

---

## Blockers

### Q1. Truck internal dimensions per type (3P / 6P / 8P) — `[BLOCKER]`
The presentation lists 11 x 6-pallet, 4 x 8-pallet and 1 x 3-pallet vehicles at Mollet. To pack realistically we need:
- Internal length x width x height (m).
- Whether double-pallet height is allowed (cases stacked on pallets vs. pallets on pallets).
- Number of fold-up curtain sections per side and their width.
- Maximum payload (kg).

> Until we have this, we use the placeholder values in `05_fleet.md`.

### Q2. Vehicle to route mapping — `[BLOCKER]`
Which truck (3P / 6P / 8P) runs each `Ruta DR`? In the PDF (NoCarga 11764300) we see vehicle V235045 / 7524KXX on route DR0027. Is there a master `Vehiculo -> Ruta` or `Vehiculo -> Transporte`? Note that drivers do up to 9 transports per day, so the same vehicle might run different routes within one day.

If not available, we will heuristically assign by typical transport volume per route.

### Q3. Is the row order in `Detalle_entrega.csv` the actual delivery order? — `[BLOCKER]`
Strong hypothesis (A1): yes. The `ZonaTransp` field progresses monotonically across stops in the transports we sampled, which matches a sensible geographic sweep. To confirm:
- Does that row order come from SAP's `No Prioridad VIAJE` (Trip Priority Number) field?
- If yes, can we get the priority field as an explicit column?
- If no, what other source captures the actual visit order?

This is the question that gates whether we have a real baseline to beat.

### Q4. Returnable to full equivalence (volume / weight) — `[BLOCKER]`
For the 45 (Material, UMA) combos without ZM040 entries (`CJ11V, CJ12V, CJ13, CJ13V, CJ15, BRL18V, BRL20V, BRL30V, BT12V, BT13, PL11V, PL12V, 3ENV*`), confirm:
- An empty `BRL30V` occupies the same outer dimensions as `ED30` (yes/no)?
- An empty `CJ13` plastic crate weighs roughly how much?
- For `3ENV0xxx` individual returnables, is there a master with their dimensions anywhere in SAP?

### Q5. Picking flexibility in the warehouse — `[BLOCKER]`
Today the picker walks the warehouse alphabetically by location (this is what `Hoja Carga` reflects). Could the picker be re-trained / re-equipped to pick **client by client** ("one cart per stop") with reasonable productivity loss? Or is the alphabetic sweep operationally untouchable?

The answer drives the entire architecture choice (centralised picking + staging vs. zonal picking carts vs. mosaic pre-pallets).

Sub-question: 76 % of the SKU range lives in `Ubic. = ZCG` (Comergrup zone, no precise rack). How is the picking sweep through ZCG today? Is it a sub-zone with its own routing, or one big bay?

### Q6. Time benchmarks — `[BLOCKER]`
- Average time to prepare one transport in the warehouse (min).
- Average unloading time per stop (min). Suspected variation by stop size.
- Average inter-stop travel time within a zone vs. between zones.
- Latest time the truck must return to base (cut-off).

Without rough numbers, we cannot compute "expected impact" for the pitch.

> Q25 below (SAP transport-lifecycle timestamps) would resolve most of this if granted.

---

## Important

### Q7. Time windows for the 90 % of clients without explicit `Horarios_Entrega` — `[IMPORTANT]`
Real coverage is **120 of 1.203 active clients** (~10 %, not the 20 % we initially thought). Acceptable defaults for the remaining ~90 %:
- Open 08:00-22:00 weekdays?
- Different default per `Sector` (HORECA vs. others)?
- Driver discretion?

We currently use A13 (08:00-22:00 weekdays) but want to confirm.

### Q8. Inter-product compatibility — `[IMPORTANT]`
Practical rules in beverage HORECA logistics:
- Glass never under barrels (crushing weight)?
- Cleaning chemicals separated from food?
- High-pressure cans vs. retornable glass?
- The cold-chain SKUs (Q14): can they share a pallet column with ambient SKUs or do they need an insulated pocket?

### Q9. Behaviour of returnables relative to free space — `[IMPORTANT]`
- After unloading at stop k, are returnables placed back in the freed slot, or in a designated truck zone (e.g. fond / fondo)?
- Does Spanish road safety regulation impose load-securing rules that limit our ability to leave gaps mid-route?

### Q10. Centre of gravity / weight balance rule used today — `[IMPORTANT]`
Is there a written rule in DDI ("heavies forward, fragiles aft", "barrels at floor only", etc.) or is it tacit? Need it as a constraint in the packing model, otherwise our outputs will look unprofessional to an experienced loader.

### Q11. Are DR routes fixed, or do clients spill across routes? — `[IMPORTANT]` (partially answered by data audit)
Data audit shows: every client has 1 home zone, every zone has 1 home route. But **873 of 1.203 clients (73 %) appear under 2+ different `Ruta` values** in `Detalle_entrega`. Hypotheses:
- The `Ruta` column reflects the operating route on that day (with overflow rebalancing), not the formal home route.
- Some chain-store clients span more than one zone in practice.

Need confirmation: is `Ruta` in `Detalle_entrega` "who actually carried it" or "who is supposed to carry it"?

### Q12. Albaran prefix decoded — `[IMPORTANT]`
Confirm: 827 = ?, 828 = ?, 841 = pure return / abono? (Heuristic from the data: 841 lines are ~all retornables-only, 827/828 mix product + retornable.)

### Q13. ZM040 dimensions: do they include the wooden pallet base + shrink-wrap? — `[IMPORTANT]`
We use 100 x 120 x 169 cm as the bounding box for an ED13 pallet. Is the 169 cm the pallet floor-to-top including the wooden base (~15 cm) or only the case stack? Affects truck-height feasibility checks.

### Q24. The "No Prioridad VIAJE" (Trip Priority Number) field — `[IMPORTANT]` (was nice-to-know, promoted)
The internal SAP system stores a per-(client, transport) suggested visit order. Can we get it as a column? Where (which SAP transaction)? This is the closest thing to a "ground truth" for the historical visit order, and resolves Q3 directly.

### Q25. Transport-lifecycle timestamps in SAP — `[IMPORTANT]` (was nice-to-know, promoted)
Are the SAP timestamps (Register / Load start / Load end / Dispatch / Transport start / Transport end) available historically? Even for a sample of routes, this would replace synthetic estimates with measured times and resolve most of Q6.

### Q26. The four counter fields in SAP (`Caja Est.`, `T.Barriles`, `TotCajaRet`, `CajaSnRet`) — `[IMPORTANT]` (was nice-to-know, promoted)
These are aggregates already computed by the system per transport. Can we get them as columns? They give us a sanity check on our line-level volume computations and a coarse 4-bucket categorisation that operations already trusts.

### Q31. Why are 65 % of (Material, UMA) entries in ZM040 with dimensions = 0? — `[IMPORTANT]`
Of 1.517 (Material, UMA) combos used in deliveries, 990 have a ZM040 row but `Longitud = Ancho = Altura = 0`. The PAL row of the same material usually has dims. Is there a richer master we are missing? Or is this just a data-quality state of ZM040 we have to live with and extrapolate from PAL using `Contador`?

### Q32. Imbalance: customer returns more empties than full units delivered — `[IMPORTANT]`
The 1:1 returnable pattern is the norm but some customers accumulate empties from previous weeks. Albaranes with prefix `841` (1.296 lines) are likely "pure returns" with no new product. How does DDI handle this volume? Is there a cap per stop? Does the driver call ahead?

### Q33. Driver 1 vs Repartidor — different field semantics? — `[IMPORTANT]`
The SAP "Modify Transport" screenshot (in `Reparto03.07.24.pptx`) shows a `Driver 1` field with a 6-digit code (e.g. 653344 — CRUANES MOLINA) different from the 850xxx / 855xxx series we see in `Detalle_entrega.Repartidor`. Are these different roles (carrier external driver vs. internal driver)? Does DDI subcontract some routes?

---

## Nice-to-know

### Q14. Cold-chain SKUs: how many and what are the rules? — `[NICE]`
We found `Ubic. = CAMARA` for `0LT0021 (CACAOLAT MINIBRIK SLIM 20CL P6 24U)` — confirmed cold chain exists. Are there more cold SKUs that ended up assigned to a different `Ubic.` (i.e. mis-tagged)? Are the trucks equipped to keep CAMARA SKUs cold during the route, or is the cold chain broken between warehouse and customer?

### Q15. Loading-dock layout in detail — `[NICE]`
We know Mollet has docks B, C, D, E, F (6-8 visible in the floor plan). Are docks specialised by route family? Can multiple trucks be loaded in parallel, and if so what's the bottleneck (forklifts, pickers)?

### Q16. What does the driver use in-cab? — `[NICE]`
Tablet, phone, paper? What system captures customer signatures? Affects what we can show to the driver in real time (and therefore the shape of our "explainable recommendation" output).

### Q17. Partial deliveries when stock-out occurs — `[NICE]`
How are they handled today? Does the driver leave a partial and come back, or refuse? Affects how robust our packing must be to last-minute changes.

### Q18. Lateral discharge in the field — `[NICE]`
Is there a regulation against opening curtains while parked illegally / on narrow streets? Does it limit which side we use at which stops? (Affects whether a lateral-only packing plan is always feasible.)

### Q19. VIP / urgent customers beyond the time-window data — `[NICE]`
Are there any priority customers we should always serve first / not delay (events, big chain promotions, hospitals)?

### Q20. GPS / route-tracking historical data with timestamps per stop — `[NICE]`
That would transform our travel-time model from synthetic to data-driven and resolve part of Q6.

### Q21. Multi-warehouse cross-docking — `[NICE]`
Is anything cross-docked through Distridam (`A0DISTRIDA`) or Comergrup (`ZCG`), or is everything physically routed through Mollet?

### Q23. Internal KPIs DDI tracks today — `[NICE]`
To align our impact metrics with theirs:
- Cases per hour of unload?
- Stops per hour?
- Km per transport?
- % truck utilisation?
- Returnables / incidents per route?

### Q27. Why do some `(Entrega, Material, UMV)` rows appear multiple times in `Detalle_entrega`? — `[NICE]`
About 9.500 lines duplicate the same (delivery, material, UMV) tuple with different quantities. Is this:
- (a) Promotion lots (same SKU at different prices on the same albaran)?
- (b) Different lotes / batches tracked separately?
- (c) SAP merging multiple sales orders onto one albaran?

Knowing this lets us decide whether to sum or keep separate when computing volume and order metrics. (Working assumption A14: sum.)

### Q28. The 14 zones defined in ZONAS but with no clients — `[NICE]`
14 `ZonaTransp.1` zones (DD13100005, 010, 036, 037, 039, 041, 042, 044, 048, 056, 057, 064, 065, 066) are defined with a route assigned but **no clients are mapped to them**. Future expansion zones? Temporarily idle? Legacy?

### Q29. Decoding `Jquia.productos` (ZM040 hierarchy) — `[NICE]`
We've inferred families from the first 4 chars (`00CZ` = cerveza, `00LM` = limpieza, `00LI` = licor, `00VE` = vino, `00RF` = refresco, `00CF` = cafe, `00AG` = agua, `00LT` = lacteos, `00AM` = alimentacion, `00ZU` = zumos, `00NV` = no-Damm, `00RA` = ratafia, parallel `01..` series) and packaging from the last 4 (`DIE4`, `RPE4`?, `13E4`, …). Could DDI confirm the exact decoding? Would let us cluster SKUs into operational families automatically.

### Q39. Are `3ENV0xxx` SKUs actually returnable, or were they bundled into "cases" in the mentor's mind? — `[IMPORTANT]` (new follow-up to Q3)
The mentor said only glass cases and barrels are returnable; cans, cleaning, spirits are not. But our data shows 20 distinct `3ENV0xxx` SKUs (cacaolat 30u, garrafa 8L, sifones, vichy 1/2, etc.) being delivered AND received back, suggesting they are returnable. Two scenarios:
- (a) The mentor simplified — `3ENV0xxx` items are returnable in the form of crates/cajas they're packed in.
- (b) The mentor was precise and `3ENV0xxx` are actually one-way; what we saw as "returnable lines" was really empties traveling within their original cases.

We need to confirm. The volume model branches on this answer.

### Q40. The 9-transport-per-day outlier in the data — `[NICE]` (new follow-up to Q5)
Mentor confirmed drivers do 1-2 transports/day. Our raw data shows up to 9 for a single (date, driver) pair. Most likely explanation: the extra "transports" are pure-return abono documents (`841...` prefix) showing up as separate transports. Worth investigating one of the 9-transport pairs in detail to confirm.

### Q41. Truck-to-route assignment by the traffic chief — `[NICE]` (new follow-up to Q5)
The truck-to-route assignment is done manually by the traffic chief without any tool. Could we get a snapshot / sample of how those manual assignments look, so we can demo our auto-assignment extension against a real comparison?

### Q42. Existing real warehouse pallets vs. the photos — `[NICE]` (new follow-up to Q4)
The mentor proposed "dedicated pallets for big & close customers". The warehouse photos show that's already happening artisanally. How often does this happen today, who decides, what's the heuristic? If we can get any record of which transports already used dedicated mixed pallets, we have a proof-of-concept inside their own data.

### Q30. The 6-digit chain client codes (BK, Taco Bell, etc.) — `[NICE]`
- Are they organisationally different (different SLAs, time windows, price lists, dock equipment)?
- Some chains have multiple locations under separate codes (BK Mollet 119751, BK Vic 118136, BK Granollers Ronda Sud 122790) — should they be planned together (multi-stop dedicated trip) or interleaved with normal HORECA?

### Q34. The 6 routes defined in ZONAS but with zero activity in our window — `[NICE]`
DR0007, DR0046, DR0047, DR0048, DR0053, DR0GEN appear in `ZONAS.csv` with assigned zones but never fire a transport in the 43-day data. Are they:
- (a) Seasonal / weekend routes not active in Jan-Mar?
- (b) Drivers on extended leave?
- (c) DR0GEN is described as "Ruta Almacen Generica DDI" — a fallback for unassigned clients?

### Q35. The generic driver "REPARTIDOR MOVI" (code 850000) — `[NICE]`
This is the only entry in `Cabecera_Transporte` whose name is a placeholder ("REPARTIDOR MOVI") rather than a person. Is this a system pseudo-driver used when the actual driver is unknown / external / temporary? How many transports does it cover and should we filter them out?

### Q36. Saturday operations — `[NICE]`
Zero transports on Saturday across the 43 days. Is this:
- Always the case at Mollet (warehouse closed)?
- A peculiarity of Jan-Mar 2026 only?
- Saturday work happens but is processed differently (not appearing in this CSV)?

### Q37. Volume unit in ZM040 `Volumen` column — `[NICE]` (likely confirmed from data, want validation)
Cross-check against the `0CF0054` example (PAL: 100x120x169 cm geometric, `Volumen = 475.2 L`). 475.2 L / 60 cases = 7.92 L per case = 24 bottles x 0.33 L liquid. So `Volumen` is **liquid volume**, not bounding-box volume — confirmed empirically. Want a single sentence from a mentor to lock this in.

### Q38. The 165 dormant clients in `Direcciones.csv` not in deliveries — `[NICE]`
1.368 rows in master vs. 1.203 in deliveries. After deduping the 165 exact-duplicate rows we get 1.203 unique clients which matches deliveries exactly. So actually no client is dormant once deduped. But: are the duplicate rows a SAP export artefact, or is there a meaning to the multiplicity (e.g. one row per active contract)? Worth one sentence.

---

## Resolved (or partially resolved by data audit + mentor session)

### From mentor session 2026-05-09

- **Q2 (visit order / Trip Priority Number) - ANSWERED, can't reconstruct historical baseline.** The `No Prioridad VIAJE` field exists in SAP but DDI says they cannot expose it to us, and they have no record of the actual order followed by the driver either. Our baseline strategy pivots: synthetic naive-geographic baseline + transparent flagging in the pitch.
- **Q3 (returnable empty vs full) - ANSWERED.** Empty cases and barrels occupy the same outer dimensions as the full ones (only weigh less). Important: the only returnable items are glass cases and barrels - cans, cleaning, spirits are NOT returnable. -> follow-up Q39 about `3ENV0xxx`.
- **Q4 (picking flexibility) - ANSWERED, opens the door.** Today alphabetical picking is mandatory because the warehouse is optimised for itself, not for the driver. But the mentor explicitly said the layout can be deconfigured for efficiency, and proposed dedicated mixed pallets for big & geographically-close customers. Our hybrid (staging + dedicated pallets) is the architecture.
- **Q5 (truck/route mapping) - PARTIAL with one big correction.** A driver does 1-2 transports per day (NOT 9 as our raw-data audit suggested). 9-20 customers per transport. The truck-to-route assignment is currently done manually by the traffic chief - this is itself an optimisation opportunity to surface in the pitch.
- **Q6 (time benchmarks) - PARTIAL with concrete numbers.** Picking time 50-60 min per truck (6P or 8P). Unloading time roughly 1.5x the loading time worst case, "depends on the client". Warehouse staff and drivers are different people running in parallel - so the cut-off constraint relaxes a lot.
- **Q7 (compatibility rules) - LIGHTLY ANSWERED.** "The warehouse order already takes care of that, I don't put a barrel on top of napkins." Effectively: the constraints are absorbed in the storage layout. Defendable in the pitch but thin if we want to be rigorous.
- **Q1 (truck dimensions) - PARTIAL.** No L x W x H or kg yet. Pocket rule: ~60 cases per pallet. Follow-up still required.
- **A11 (one trip per day) - DOUBLE-CORRECTED.** Mentor confirms 1-2 trips/day, not the 9 we saw in raw data. The raw-data outliers are likely `841...` abono albaranes inflating the count. Worth investigating but not a blocker.

### From data audit

- **A10 (no refrigerated cargo) - REFUTED.** SKU `0LT0021` (Cacaolat minibrik) sits in `Ubic. = CAMARA`. Cold chain exists but is small. Q14 follow-up pending.
- **Time-window coverage 20 % - CORRECTED to ~10 %.** Of 240 deudores in `Horarios`, only 120 are active in our deliveries (rest are dormant accounts with stale schedule rules).
- **"All clients are 10-digit codes" - REFUTED.** 23 of 1.203 active clients are 6-digit chain codes (BK, Taco Bell, UDON, CIRSA, EUREST, DISTRIDAM…). Treat as string. -> Q30 follow-up.
- **`ZONAS.csv` schema - CLARIFIED.** Two unrelated tables glued side-by-side; cols 2/3/6/7/8/9 are blank spacers. See `09_data_quality.md` Trap 3.
- **Material coverage in ZM040 - CLARIFIED.** 437 / 1.517 (Material, UMA) combos have geometric dims directly; 990 require extrapolation from PAL; 45 (returnables) need mapping to the full counterpart. See `09_data_quality.md` Trap 7.
- **Cabecera column semantics - CLARIFIED.** `Unnamed: 5` holds driver name; `Destinatario mcia.` is client code in Cabecera but driver name in Detalle. See `09_data_quality.md` Trap 1-2.
- **Direcciones duplicates - CLARIFIED.** 165 rows are exact duplicates of other rows; dedupe on `Cliente` to recover 1.203 unique clients matching deliveries exactly.
- **Mollet warehouse coordinates - CLARIFIED.** C/ Moli de Can Bassa, Nau Damm 1, Pol. Ind. Can Magarola, 08100 Mollet del Valles. Approx 41.55 N, 2.21 E.

---

## Removed

- ~~Q22 (weather effects on unload time)~~ — immaterial at our modelling resolution; not worth asking.

---

## Research backlog (for the multi-agent phase)

These are not questions for the user; they're research tasks for parallel agents once the basics are set:

- R1. State of the art in **VRPSPD with time windows** + side-loading constraints.
- R2. Pickup-and-delivery distribution case studies in beverage HORECA (Coca-Cola, Mahou-San Miguel, Heineken, Diageo, Pepsi).
- R3. **3D bin packing with LIFO + open-side access** algorithms.
- R4. **Class-based storage assignment** for warehouse layout (could justify Q5's "is re-layout possible?").
- R5. Open-source toolchains — OR-Tools recipes, jsprit, VROOM, OptaPlanner, pyVRP.
- R6. Visualisation references — TMS / WMS dashboards, particularly load-plan visualisations from real industry products.
- R7. Sensitivity analysis methodologies for VRP with uncertain demand and time windows.
- R8. Sustainability impact metrics standardised in distribution (CO2 per stop, per km, per case).
