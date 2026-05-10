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

## Cost / objective function (revised after mentor session 2)

The **central message from the mentor** is: do not minimise delivery cost alone. Minimise the **joint** picking + delivery cost.

> "Nosotros no estamos buscando lo más óptimo para repartir, sino que estamos buscando un equilibrio. Lo más óptimo posible para cargar y lo más óptimo posible para repartir."

If our pitch promises "30 % faster routes" but the picking time doubles, the mentor will reject it. So the function is:

```
total_cost(plan) =
   α · picker_trip_cost(load_plan)     <- warehouse side: walking distance
                                           in the picker's sweep, plus extra
                                           trips for "dedicated" customer carts
 + β · km_driven                       <- fuel, time, emissions
 + γ · sum(handling_cost(stop))        <- per-stop penalty: cases out of place,
                                           pallet reshuffles needed, depth from
                                           the open curtain
 + δ · time_late_per_stop              <- service quality (only for clients
                                           with explicit windows in Horarios)
 + ε · cluster_split_penalty           <- penalty when our route splits a tight
                                           customer cluster into multiple truck
                                           stops (the "park and walk" pattern)
 + ζ · fragile_under_heavy_penalty     <- "cases on barrels" is soft, not hard
```

### What's NOT in the function

- **No kg constraint and no kg penalty.** The mentor said "ignore weight, focus on cases". So we don't model mass at all.
- **No hard return-time deadline.** Return-by-X is soft. We capture it inside `β · km_driven` (longer route = more km = more cost) but never as an infeasibility.

### What IS now a hard constraint

- **`sum(cases_on_truck) <= max_cases(truck_type)`** — the binding capacity constraint.
- **`sum(pallets_on_truck) <= 3 / 6 / 8`** — pallet count cap by truck type.
- **`whole_pallet_stops_per_route <= 4`** — operational cap from the mentor (2-4 max in real life).
- **driver license category compatible with assigned truck** — level 1 / 2 / 3 from the SAP driver master must match the truck size.
- **(driver, truck) is a fixed input pair** — the assignment is stable and is given to the solver, not solved.

Where:
- α, β, γ, δ, ε, ζ are tunable weights — and crucially `α` (warehouse cost) must be high enough that we don't propose plans that murder the warehouse.
- `picker_trip_cost` is computed as: L1 distance the picker walks for the global sweep + extra walks per "dedicated cart" customer.
- `handling_cost` per stop: combines (# distinct columns the driver must touch in the truck) + (depth from the nearest open curtain) + (estimated walking distance inside the customer's premises if known).
- `cluster_split_penalty` triggers when our route crosses through a cluster zone twice or interleaves customers from different clusters — the driver would prefer a clean "park once, do the cluster, leave".

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
