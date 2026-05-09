# 04 — Warehouse Mollet

What we know about the physical warehouse where loads get prepared.

---

## Address & code
- DDI Mollet — Centre **D131**.
- C/ Molí de Can Bassa, Nau Damm 1, Pol. Ind. Can Magarola, 08100 Mollet del Vallès, Barcelona.
- Approximate coordinates: 41.55 N, 2.21 E.

---

## Position counts (from `Layout Mollet.xlsx → RESUMEN DDI MOLLET` sheet)

| Zone type | SUELO | ALT(3) | ALT(4) | ALT(9) | TOTAL |
|---|---:|---:|---:|---:|---:|
| Estantería (racking) | 342 | 348 | 504 | – | **1.194** |
| Estantería compacta (drive-in) | 10 | – | – | 230 | **240** |
| SUELO (floor positions) | 151 | 246 | – | 224 | **621** |
| Exterior approx. | 105 | 200 | – | – | **305** |

**Total positions: ~2.360** (interior 2.055 + exterior 305).

The "ALT(N)" labels indicate stacking levels (height tiers) at that position.

---

## Location codes

Pattern: `[ÁREA][PASILLO][NUM][NIVEL][ALT]` — e.g. `FA05A2`, `AC07A1`, `EB02A1`, `BC04A3`.

Decoding (inferred from the patterns we see in `Materiales_zubic` and the loading sheet):
- 1st letter (`A`–`F`): warehouse area / hall.
- 2nd letter (`A`/`B`/`C`): aisle within the area.
- 2-digit number (`01`–`30`): position along the aisle.
- 4th letter (`A`/`B`): shelf side or sub-position.
- Last digit (`1`/`2`/`3`): vertical level (1 = floor, 2/3 = upper).

### Special codes (not following the geometric pattern)

| Code | Meaning |
|---|---|
| `A0DISTRIDA` | Product from **Distridam** (Damm subsidiary handling other lines) |
| `ZCG` | Product from **Comergrup** (joint distribution partner). Sample materials: cleaning, cutlery, snacks, spirits |
| `PLV` | POS / marketing material (Punto de Venta) |
| `ENVASE` | Returnable empties storage |
| `AAAAAA` | Default / unassigned |

When the loading sheet says `ZCG`, it doesn't tell the picker a precise rack — it's a "go to the Comergrup zone and pick it from there" instruction.

---

## Warehouse splits

From `Materiales_zubic.csv`:

| Almacén | SKU count | Likely role |
|---|---:|---|
| 0001 | 823 | Main interior racking |
| 0005 | 498 | Secondary / overflow / Comergrup pool |
| 0002 | 1 | Edge case (one SKU only — possibly anecdotal) |

All 1.489 SKUs sit in centre D131. None are split across centres (Mollet only).

---

## Loading docks (from the public presentation, slide 3)

The warehouse floor plan shows:
- A loading area with **docks labelled B, C, D, E, F** (red-shaded). At least **6–8 dock positions are visible**.
- Trucks are positioned at these docks for loading; once full, they drive out.
- Implication: multiple trucks can be loaded in parallel. Picking a route can collide with the routes of other trucks (shared aisles, shared forklifts).

The diagram also shows:
- Upper warehouse zone: parallel rows of racking with aisles between them (orange/light-blue colour-coded — orange = product, light-blue = picking/transit).
- Lower zone: extra racking, possibly returnables / lower-rotation.
- A dashed red perimeter line in the upper part — separating an isolated zone (maybe Comergrup `ZCG`).

---

## What this means for the load model

1. **The picker walks an aisle path.** Locations like `AA02A1 → AA03A1 → AA04A1` are physically consecutive. The current "pick by reference" approach exploits this: every line of the loading sheet is the next physical bay over, so the picker walks once past everything.
2. **A "pick by client" model would multiply trips.** If each client's products are spread across `AA / AC / BA / CB / DA / EA / FA / ZCG`, and we want them grouped in the truck *by client*, the picker has to make 18 round-trips through the warehouse instead of 1 sweep. That's a hard cost we must quantify.
3. **A hybrid approach is forced**: keep the picker's sweep efficient *somehow* (zone-coloured pallets? multi-zone picking carts?), then re-arrange at the truck-loading bay.
4. **Lateral access at the truck side** means the picker doesn't have to load only by the back. They can load the truck progressively from the side, which permits a "column per client" layout if the warehouse's bay gives enough working space.

---

## Photo evidence (Fotos Mollet)

What's visible across the 47 photos (notable observations):
- Tall racking, mostly 4 levels of pallets.
- Big floor blocks of red Estrella crates (CJ13 / ED13 cases) and blue Veri crates near the loading area.
- Hyster + Jungheinrich forklifts and electric pallet jacks in active use.
- Red Damm trucks (medium duty, flatbed with closed box and lateral lonas plegables) parked at the docks during loading.
- A clearly visible **mosaic-style mixed pallet for one client** in one photo: layers of Estrella + Veri + Vichy + multi-brand cases stacked into a stable tower. → Evidence that **mixed pre-pallets per client already happen**, manually, today.
- An exterior open zone with stainless 30 L barrels (BRL30) and shrink-wrapped pallets stacked outside.
- A "returnable empties" zone where empty crates pile up before going back to the brewery.
