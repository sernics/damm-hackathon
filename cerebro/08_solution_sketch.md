# 08 — Solution Sketch (architecture draft)

Not a final design. A starting point that we can argue with and modify as research and feedback come in.

---

## Layered architecture

```
┌──────────────────────────────────────────────────────────────────┐
│   PRESENTATION LAYER                                             │
│   - Map view of the route                                        │
│   - 2D / 3D side-view of the truck (per-customer colour blocks)  │
│   - Operational dashboard (KPIs vs baseline)                     │
│   - Explainability panel (why this order, why this layout)       │
└──────────────────────────────────────────────────────────────────┘
                                ▲
┌──────────────────────────────────────────────────────────────────┐
│   OPTIMISATION LAYER                                             │
│   - Routing solver (VRPSPD with time windows)                    │
│   - Packing solver (2D + light 3D, LIFO-friendly per side curt.) │
│   - Multi-objective wrapper (Pareto: km, time, search-cost,      │
│     picker-trip-cost, weight balance, fragility)                 │
└──────────────────────────────────────────────────────────────────┘
                                ▲
┌──────────────────────────────────────────────────────────────────┐
│   FEATURE LAYER                                                  │
│   - Geocoded clients (lat/lng from Calle + CP + Población)       │
│   - Estimated travel times (OSRM / OpenRouteService)             │
│   - Per-line cubic volume, weight, fragility, family             │
│   - Returnable mapping (CJ13 ↔ ED13, BRL30V ↔ ED30, …)           │
│   - Time windows (240 clients) and "default open" for the rest   │
│   - Warehouse location for every line                            │
└──────────────────────────────────────────────────────────────────┘
                                ▲
┌──────────────────────────────────────────────────────────────────┐
│   DATA LAYER (ETL)                                               │
│   merged dataset = Detalle ⨝ ZM040 ⨝ Materiales_zubic ⨝ ZONAS   │
│                    ⨝ Direcciones ⨝ Horarios ⨝ Cabecera          │
│   exported as parquet for fast iteration                         │
└──────────────────────────────────────────────────────────────────┘
                                ▲
                Raw CSVs / XLSX / PDFs / photos
```

---

## Core decision: which solver pattern

Two possible framings, in increasing complexity. We pick based on time/scope.

### A. Sequential (cleaner for hackathon, easier to explain)

1. **Step 1 — Routing.** Solve VRPSPD with time windows over the day's deliveries → get a stop sequence.
2. **Step 2 — Packing.** Given the sequence, solve a packing problem that lays the load out in column-by-column order matching the sequence.
3. **Step 3 — Picking guidance.** Given the packing plan, generate a warehouse pick list that respects warehouse efficiency (zone batching) but produces "client-tagged" stacks at the loading dock.

Pros: clean separation, easy to debug, easy to explain in pitch.
Cons: routing decisions ignore packing infeasibilities (rare, given lateral access).

### B. Joint (technically nicer, harder to deliver)

Solve routing + packing as one optimisation. Use a meta-heuristic (LNS, GA, ALNS) where each candidate is a (route, packing) pair and the cost function aggregates km + time + ergonomics + picker effort.

Pros: theoretically optimal trade-offs. Pros for the "creativity" criterion (15 %).
Cons: hard to ship in 1 hackathon weekend.

→ **Recommendation: build A first, demonstrate it works, then layer B for the pitch as "what's possible if we keep going".**

---

## Tooling shortlist

| Layer | Library / tool | Why |
|---|---|---|
| Routing | **OR-Tools** (Google) | Industry standard for VRPTW / VRPSPD. Free. Python bindings. |
| Routing alternative | **VRPy / pyVRP** | Lighter, more pythonic for medium instances. |
| Packing | **py3dbp** + custom LIFO constraints, or hand-roll a 2D-grid placement | py3dbp is a starting point but its LIFO support is weak; we will probably need a small custom packer. |
| Geocoding | **Nominatim** (OpenStreetMap, free) with local cache | 1.203 clients — feasible to geocode locally with rate limit. |
| Travel times | **OSRM** (self-hosted or public demo server) or **OpenRouteService** (free tier) | Cheaper than Google Maps API. |
| Visualisation | **Folium / Leaflet** (map), **matplotlib / Plotly** (truck side-view), **Streamlit** (dashboard) | Familiar, hackathon-friendly. |
| ETL & analysis | **pandas + duckdb + parquet** | Detalle_entrega has 82 k rows — pandas works, DuckDB is faster for joins. |

---

## Cost / objective function (first draft)

```
total_cost(plan) =
   α · km_driven                      ← fuel, time, emissions
 + β · time_late_per_stop              ← service quality
 + γ · sum(handling_cost(stop))        ← per-stop penalty: how many cases /
                                          how many "out-of-place" SKUs has
                                          the driver to move at this stop
 + δ · picker_trip_cost(load_plan)     ← cost of preparing this layout in
                                          the warehouse (jumps in pick path)
 + ε · weight_imbalance_penalty
 + ζ · fragile_under_heavy_penalty
```

Where:
- α, β, γ, δ, ε, ζ are tunable weights.
- `handling_cost` per stop is approximated by: `(# distinct columns the driver must touch)` + `(deepness from the nearest open curtain)`.
- `picker_trip_cost` is the **L1 distance** in warehouse-coordinate space between consecutive picks of the same client cart.

This separates the four big interests clearly and lets us produce a Pareto front the jury can interpret.

---

## Visualisation, three views

1. **Map view.** Folium / Leaflet. Numbered stops, colour by zone. Toggle "current order" vs "optimised order" to show the impact.
2. **Truck side view.** A grid of pallet/case footprints colour-coded by destination customer + small icons for retornable. Slider to scrub through the route: *"after stop 3, here's how the truck looks"*.
3. **Warehouse pick view.** The Mollet floor plan with a path drawn for the picker, colour-segmented by which client each set of picks goes to. Show "if we pick by client today, here's the path; vs by reference, here's the path" — quantitative comparison.

These three together tell the full story: route, truck, warehouse — exactly the three constituencies the brief mentions.

---

## Baseline to beat

The simplest baseline is **the current process**, which we can reconstruct from the data:
- Route order ≈ row order in `Detalle_entrega.csv` (assumption A1) or zone order DD13100xxx ascending.
- Load order = warehouse `Ubicación` alphabetical.

Compute baseline metrics:
- Total km of the route order (via OSRM).
- Estimated handling cost (sum of "search distance" per stop, modelled as: how many `Ubicación` blocks separate the products of stop-k from each other on the loading sheet).
- Picker trip length (1 sweep — already optimal for warehouse).

Optimised metrics:
- Total km (should be ≤ baseline by a few %).
- Handling cost (should drop dramatically).
- Picker trip length (will increase — quantify how much).
- Net composite cost (should drop overall; the trade-off is the story).

---

## Multi-agent research plan

When we're ready to deepen the technical foundations, spawn parallel agents on:

1. **VRPSPD with side-loading and 3D constraints** — papers, OR-Tools recipes.
2. **Pickup-and-Delivery Problem (PDP)** literature for beverage / HORECA distribution — case studies (Coca-Cola, Mahou-San Miguel, Heineken).
3. **3D bin packing with LIFO + open-side access** — algorithmic state of the art.
4. **Warehouse layout optimisation by frequency / affinity** — class-based storage assignment.
5. **Open-source toolchains for combined route + load** — jsprit, VROOM, OptaPlanner, alternative OR-Tools recipes.
6. **Visualisation references** — how do real WMS / TMS dashboards show truck loads and routes?

Tracked in `QUESTIONS.md` as the "research backlog".

---

## Risk register (first pass)

| Risk | Likelihood | Mitigation |
|---|---|---|
| Geocoding fails for a chunk of addresses | Medium | Manual fallback for top 20 % of clients; otherwise drop them from the demo. |
| OR-Tools VRPSPD doesn't converge for 30+ stops with TW | Low | Use OR-Tools "guided local search" with 60-second cap. |
| Packing solver too slow | Medium | Start with 2D placement (column = stop). Avoid full 3D. |
| Stakeholders ask "but what about Mondays/Fridays peak"? | Low | Demo on a peak day to be safe (Friday with 20+ transports). |
| Jury asks for actual truck dimensions and we said "assumed" | Medium | Be honest about it in the pitch and present sensitivity analysis. |
| Demo data exposes a real customer name | High | Anonymise client names in any external materials. |
