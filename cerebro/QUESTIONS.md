# Open Questions

Living list. **Status legend:** 🔴 blocker / 🟠 important / 🟡 nice-to-know.
When a question gets resolved, move it to the "Resolved" section below with the answer.

---

## 🔴 Blockers (we cannot model the problem well without these)

### Q1. Truck internal dimensions per type (3P / 6P / 8P)
The presentation lists 11 × 6-pallet, 4 × 8-pallet and 1 × 3-pallet vehicles at Mollet. To pack realistically we need:
- Internal length × width × height (m).
- Whether double-pallet height is allowed.
- Number of fold-up curtain sections per side and their width.
- Maximum payload (kg).

> Until we have this, we use the placeholder values listed in `05_fleet.md`.

### Q2. Vehicle ↔ route mapping
Which truck (3P / 6P / 8P) runs each `Ruta DR`? In the PDF (NºCarga 11764300) we see vehicle V235045 / 7524KXX on route DR0027. Is there a master `Vehículo → Ruta` we can get?

If not, we'll heuristically assign by typical transport volume per route.

### Q3. Is the row order in `Detalle_entrega.csv` the actual delivery order?
Strong hypothesis (A1) it is, given the monotonic zone progression we observed. To confirm:
- Does that row order come from SAP's `Nº Prioridad VIAJE` field?
- If yes — can we get that field as an explicit column?
- If no — what other source captures the actual visit order?

### Q4. Returnable ↔ full equivalence (volume / weight)
For the 45 SKUs without ZM040 entries (CJ13, CJ15, BRL30V, 3ENV*, …), is our heuristic mapping in `06_returnables.md` correct? Specifically:
- Does an empty BRL30V occupy exactly the same dimensions as ED30 (yes/no)?
- Does an empty CJ13 plastic crate weigh ~ how much?
- For 3ENV0xxx individual returnables, is there a master with their dimensions?

### Q5. Picking flexibility
Today the picker walks the warehouse alphabetically by location. Could the picker be re-trained / re-equipped to pick **client by client** ("one cart per stop") with reasonable productivity loss? Or is the alphabetic sweep operationally untouchable?

The answer drives the entire architecture choice (centralised picking + staging vs. zonal picking carts vs. mosaic pre-pallets).

### Q6. Time benchmarks
- Average time to prepare one transport in the warehouse (min).
- Average unloading time per stop (min).
- Average inter-stop travel time within a zone vs. between zones.
- Latest time the truck must return to base (cut-off).

Without rough numbers, we can't compute "expected impact" for the pitch.

---

## 🟠 Important (affect the quality of the solution)

### Q7. Time windows for the 81 % of clients without explicit `Horarios_Entrega`
Acceptable defaults:
- Open 08:00–22:00 weekdays?
- Different default per `Sector` (HORECA vs. others)?
- Driver discretion?

→ We currently use A13 (08:00–22:00) but want to confirm.

### Q8. Inter-product compatibility
Practical rules in beverage HORECA logistics:
- Glass never under barrels (crushing weight)?
- Cleaning chemicals separated from food?
- High-pressure cans vs. retornable glass?
- Any product with strict temperature / humidity / vibration limits?

### Q9. Behaviour of returnables relative to free space
- After unloading at stop k, are returnables placed back in the freed slot, or in a designated truck zone (e.g. fond)?
- Does Spanish road safety regulation impose load-securing rules that limit our ability to leave gaps mid-route?

### Q10. Centre of gravity / weight balance rule used today
Is there a written rule in DDI ("heavies forward, fragiles aft", "barrels at floor only", etc.) or is it tacit?

### Q11. Are DR routes fixed, or do clients spill across routes? (ANSWERED PARTIALLY BY DATA AUDIT)
Data audit shows: every client has 1 home zone, every zone has 1 home route — but **873 / 1.203 (73 %) of clients show up under 2+ different `Ruta` values** in `Detalle_entrega`. Hypotheses:
- The `Ruta` column reflects the operating route on that day (with overflow rebalancing), not the formal home route.
- Some chain-store clients span more than one zone in practice.

Need confirmation: is `Ruta` in `Detalle_entrega` "who actually carried it" or "who is supposed to carry it"?

### Q12. Albarán prefix decoded
Confirm: 827 = ?, 828 = ?, 841 = pure return / abono?

### Q13. ZM040 dimensions: do they include the wooden pallet base + shrink-wrap?
We use 100×120×169 cm as the bounding box. Is the 169 cm the pallet floor-to-top including the wooden base (~15 cm) or only the case stack?

---

## 🟡 Nice-to-know

### Q14. Cold-chain SKUs — confirmed yes; how many and what are the rules?
We found `Ubic. = CAMARA` for `0LT0021 (CACAOLAT MINIBRIK SLIM 20CL P6 24U)`. Are there more cold SKUs that ended up assigned to a different `Ubic.`? Are the trucks equipped to keep CAMARA SKUs cold (e.g. insulated bag inside the box) or is the cold chain broken between warehouse and customer?

### Q15. Confirm Mollet warehouse coordinates (lat/lng) and the depot's actual loading-dock layout.

### Q16. What does the driver use in-cab? Tablet, phone, paper? What system captures customer signatures?

### Q17. How are partial deliveries handled when stock-out occurs?

### Q18. Lateral discharge in the field: is there a regulation against opening curtains while parked illegally / on narrow streets? Does it limit which side we use at which stops?

### Q19. Are there VIP / urgent customers beyond the time-window data?

### Q20. Do we have any GPS / route-tracking historical data with timestamps per stop? That'd transform our travel-time model from synthetic to data-driven.

### Q21. Is multi-warehouse cross-docking real (Distridam, Comergrup) — or is everything routed through Mollet?

### Q22. Weather effects: rain → slower unload? Probably immaterial but…

### Q23. Internal KPIs DDI tracks today
To align our impact metrics with theirs:
- Cases per hour of unload?
- Stops per hour?
- Km per transport?
- % truck utilisation?
- Returnables / incidents per route?

### Q24. The "Trip Priority Number" field
Can we get it as a column? Where (which SAP transaction)?

### Q25. The transport lifecycle timestamps
Are the SAP timestamps (Register / Load start / Load end / Dispatch / Transport start / Transport end) available historically? Even for a sample of routes, this would give us real picking and trip durations.

### Q26. The four counter fields in SAP (`Caja Est.`, `T.Barriles`, `TotCajaRet`, `CajaSnRet`)
These are aggregates already computed by the system. Can we get them per transport? They'd be a useful sanity check on our line-level computations.

### Q27. Why do some `(Entrega, Material, UMV)` rows appear multiple times in `Detalle_entrega`?
About 9.500 lines duplicate the same (delivery, material, UMV) tuple with different quantities. Is this:
- (a) Promotion lots (same SKU at different prices on the same albarán)?
- (b) Different lotes / batches tracked separately?
- (c) SAP merging multiple sales orders onto one albarán?

Knowing this lets us decide whether to sum or keep separate when computing volume and order metrics.

### Q28. The 14 zones defined in ZONAS but with no clients
14 `ZonaTransp.1` zones (DD13100005, 010, 036, 037, 039, 041, 042, 044, 048, 056, 057, 064, 065, 066) are defined with a route assigned but **no clients are mapped to them**. Are these:
- Future zones reserved for expansion?
- Zones whose clients are temporarily idle (closed venues, seasonal)?
- Just legacy / cleanup needed?

### Q29. Decoding `Jquía.productos` (ZM040 hierarchy)
We've inferred families from the first 4 chars (`00CZ` = cerveza, `00LM` = limpieza, …) and packaging from the last 4 (`DIE4`, `RPE4`?, …). Could DDI confirm the exact decoding? It would let us cluster SKUs into operational families (frágil, pesado, retornable, refrigerado, …) automatically.

### Q30. The 6-digit chain client codes (BK, Taco Bell, etc.)
- Are they organisationally different (different SLAs, time windows, price lists, dock equipment)?
- Some chains have multiple locations (BK Mollet, BK Vic, BK Granollers Ronda Sud) under separate codes — should they be planned together (multi-stop dedicated trip) or interleaved with normal HORECA?

---

## ✅ Resolved (or partially resolved by data audit)

- **A10 (no refrigerated cargo) → REFUTED.** SKU `0LT0021` (Cacaolat minibrik) sits in `Ubic. = CAMARA`. Cold chain exists but is small. A14 follow-up question pending.
- **A11 (one trip per day) → REFUTED.** 30 % of (date, driver) pairs run multiple transports per day; max 9. Routing horizon stays per-transport.
- **Time-window coverage 20 % → CORRECTED to ~10 %.** Of 240 deudores in `Horarios`, only 120 are active in our deliveries (the rest are dormant accounts with stale schedule rules).
- **"All clients are 10-digit codes" → REFUTED.** 23 of 1.203 active clients are 6-digit chain codes (BK, Taco Bell, UDON, CIRSA, EUREST, DISTRIDAM…). Treat as string. → Q30 follow-up.
- **`ZONAS.csv` schema → CLARIFIED.** Two unrelated tables glued side-by-side; cols 2/3/6/7/8/9 are blank spacers. See `09_data_quality.md` Trap 3.
- **Material coverage in ZM040 → CLARIFIED.** 437 / 1.517 (Material, UMA) combos have geometric dims directly; 990 require extrapolation from PAL; 45 (returnables) need mapping to the full counterpart. See `09_data_quality.md` Trap 7.

---

## Research backlog (for the multi-agent phase)

These aren't questions for the user; they're research tasks for parallel agents once the basics are set:

- R1. State of the art in **VRPSPD with time windows** + side-loading constraints.
- R2. Pickup-and-delivery distribution case studies in beverage HORECA (Coca-Cola, Mahou-San Miguel, Heineken, Diageo, Pepsi).
- R3. **3D bin packing with LIFO + open-side access** algorithms.
- R4. **Class-based storage assignment** for warehouse layout (could justify Q5's "is re-layout possible?").
- R5. Open-source toolchains — OR-Tools recipes, jsprit, VROOM, OptaPlanner, pyVRP.
- R6. Visualisation references — TMS / WMS dashboards, particularly load-plan visualisations from real industry products.
- R7. Sensitivity analysis methodologies for VRP with uncertain demand and time windows.
- R8. Sustainability impact metrics standardised in distribution (CO₂ per stop, per km, per case).
