# 05 — Fleet

What we know about the trucks (and what we're still guessing).

---

## Vehicle composition at Mollet (from the public presentation)

| Type | Pallet capacity | Quantity at Mollet | Likely use |
|---|---:|---:|---|
| Large truck | 8 pallets | 4 | Largest / longest routes |
| Standard truck | 6 pallets | 11 | Most routes (default) |
| Van | 3 pallets | 1 | Small / urgent / coffee |
| **Total** | — | **16** | |

DDI's full national fleet is **470 vehicles** across 33 centres. We work with the Mollet sample.

---

## What we know about the trucks (visual evidence)

From the photos in `Fotos Mollet/` and from the side panels visible:

- **Cab type**: medium-duty rigid trucks (Mitsubishi Fuso Canter / Renault D / similar — the brand is partly visible). **Not** semi-trailers.
- **Box type**: closed cargo box, mounted on the chassis. Roof rigid, walls partly rigid + partly with **lateral tarpaulins (lonas) that fold up to expose pallets from the side**.
- **Floor of the box**: flat, single-level pallet floor. No mezzanine visible. Pallets are placed on the box floor in a single row of height (no apparent palletised stacking — but loose cases can be stacked on top of pallet bases).
- **Rear access**: full-height rear door (curtain or hinged) — for loading/unloading from the back as well.
- **Visible licence plates**: e.g. `7524KXX`, `2EY498` — just confirms each vehicle has a unique plate.
- **Tractor codes** in SAP: `V2xxxxx` (e.g. `V235045`).

---

## Lateral access — why it matters

The key operational feature: the side curtains can be opened along the entire length of the truck, exposing every pallet. This means:
- The driver doesn't have to remove every pallet in order to reach one in the middle.
- Loading order at the warehouse can be **per pallet column**, not per "depth into the truck".
- A solid load model can therefore think of the truck as a **2D grid** (length × width) rather than a 1D LIFO stack.

> Caveat: the tarpaulin opens, but the cargo is still secured by straps, dunnage and load bars. Removing a single pallet from the middle still costs time. The model should weight "easy access" heavier for stops near the start of the route.

---

## What we're still guessing (assumed values)

These are placeholder defaults for our first iteration. **Tracked as Q1 in `QUESTIONS.md`.**

| Parameter | 6-pallet truck | 8-pallet truck | 3-pallet van |
|---|---|---|---|
| Internal length | ~ 4.20 m | ~ 5.80 m | ~ 3.00 m |
| Internal width | ~ 2.30 m | ~ 2.40 m | ~ 1.80 m |
| Internal height | ~ 2.30 m | ~ 2.50 m | ~ 1.90 m |
| Pallet base | 1.20 × 1.00 m (Euro/Damm) | same | same |
| Stacking levels for cases | 2 (cases on top of palletised cases) | 2 | 1–2 |
| Max payload | ~ 3.500 kg | ~ 5.500 kg | ~ 1.500 kg |
| Lateral curtains | both sides, full length | both sides, full length | one or both sides |

These need confirmation; they're consistent with European medium-duty trucks of that pallet capacity.

---

## Truck → route mapping (unknown)

We do **not** have a column anywhere that tells us which physical truck did which transport. From the PDF (NºCarga 11764300, vehicle V235045 / 7524KXX, route DR0027) we have one pairing; we don't have the rest.

Likely heuristics if we have to guess (and we'll have to):
- Match a route's typical transport volume (m³) to the smallest truck that fits it.
- Route DR0027, DR0050 and DR0051 have the highest average volumes per transport (>500 L geometric on our rough estimate) — likely run on 8-pallet trucks.
- The coffee route DA0216 has tiny per-transport volumes — almost certainly the 3-pallet van.

> Tracked as Q2 in `QUESTIONS.md`.

---

## Load constraints we should respect (even with imperfect data)

1. **Don't put fragile (vidrio) under heavy (barriles).** Barrels are 30 kg each; a stack of a barrel pallet can crush bottles below it.
2. **Don't put slim cases under big pallets.** Stability matters.
3. **The driver has to open lonas in the same order as stops.** If the curtain has 3 sliding sections (front, middle, rear), placing client-A's products only in the middle section is fine for stop 1; placing them spread is bad.
4. **Centre of gravity.** A heavy load all on one side makes the truck unstable in turns. Alternate pallet weights across the long axis where possible.
5. **Returnables go back on the truck.** An empty CJ13 occupies the same dimensions as a full ED13 (same plastic crate). This means: as a stop is unloaded, the empties usually fit back into the freed space without extra capacity needed. Net volume effect over the route ≈ neutral when retornable rate is high (~78.8 % of stops).

---

## Implication for the model

We model the truck cargo space as a **2D grid** (length × lateral position), each cell holding a "stack" (pallet base + cases stacked on top). The routing solver decides the order of stops; the packing solver maps each delivery to a contiguous block in the grid such that:
- Block(stop k) is reachable through a side curtain at stop k without disturbing block(stop k+1, k+2, …).
- Returnables retrieved at stop k are placed in the now-free block(stop k).
- Total weight balance and fragile-vs-heavy ordering are respected.

This is a **mixed VRPTW + 3D-LIFO bin-packing** problem. The 1D LIFO assumption is too strong because lateral access exists; the full 3D bin-packing is overkill because cases palletise nicely. A 2D + light-3D model is the sweet spot.
