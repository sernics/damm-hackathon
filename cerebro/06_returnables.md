# 06 — Returnables (the reverse-logistics flow)

This is the variable that defines the challenge. ~60 % of what's delivered is also picked up empty. Without modelling this, any "perfect" loading plan is fiction.

---

## The 1:1 pattern (verified empirically)

Every full case delivered to a customer is matched on the same albarán by an empty case picked up. Example from delivery `828075878` (XARRUP BAR):

```
Material   Denominación                        Cantidad  UMV
ED15LN     ESTRELLA DAMM 1/5 LN                  3       CAJ
CJ15       CAJA DAMM+BOT.1/5RET VACÍO …          3       CAJ   ← matching empty
FD13       FREE DAMM 1/3 RET.                    1       CAJ
CJ13       CAJA DAMM+BOT.1/3RET VACÍO …          1       CAJ   ← matching empty
VO13       VOLL-DAMM 1/3 RET.                    2       CAJ
CJ13       CAJA DAMM+BOT.1/3RET VACÍO …          2       CAJ   ← matching empty
…
```

The customer pays for the full content (`ED15LN`) and is credited the deposit on the empty (`CJ15`). Physically, the driver hands them the new case and takes back the empty into the truck.

---

## What counts as a returnable

By prefix / pattern of the SKU code:

| Pattern | Example | What it is |
|---|---|---|
| `CJ13`, `CJ15`, `CJ12V`, `CJ14` | `CJ13` | Empty plastic case for retornable bottles (1/3, 1/5, etc.) |
| `BRL30V`, `BRL20V`, `BRL18V` | `BRL30V` | Empty stainless-steel barrel |
| `3ENV0xxx` | `3ENV0029`, `3ENV1281` | Empty individual container (e.g. cacaolat 30 u, garrafa 8 L, vidrio 1/3) |
| `PL11V`, `PL12V` | `PL11V` | Empty plastic crate (PET smaller formats) |
| `*V` (suffix) | `CJ12V` | "Vacío" suffix marker |

In the data:
- **31 % of all albarán lines** are returnable items by this rule.
- **78.8 % of deliveries** carry at least one returnable line.
- The biggest returnable mover is `CJ13` (46.239 cases over 43 days).

---

## What it implies for loading

### Volume balance over a route

If a stop receives X cases of `ED13` and returns X empties of `CJ13`, the net change in occupied truck volume after that stop is **zero in the limit** (the empty goes back into the same plastic crate the full came in).

Reality is messier:
- About 22 % of deliveries have **no** retornables (water in PET, cans, coffee, wine, spirits, cleaning…). Those stops free space without returning anything.
- Some retornables (e.g. `BRL30V`) come back without an exact 1:1 match — the customer might return more than they receive (clearing accumulated empties).
- Empty barrels are slightly lighter than full ones but **the same outer dimensions**.

For volume planning purposes, a reasonable model is:
> **Net volume drop per stop = (lines without retornable) × line volume.**
> Lines with retornable contribute zero to volume drop, contribute weight drop only.

This is what justifies a single-trip operation: you don't need a parallel "returnables-only" truck, because the same physical space turns over.

### Position planning during the route

Since the empty case fits into the slot of the delivered full case, the natural layout is:
1. The driver opens the side curtain at stop k.
2. They take out the *block of pallets/cases assigned to stop k*.
3. They *replace* it with the empties received from the customer.
4. Move to stop k+1.

The "block" can be:
- A whole pallet (fast handling) — works for big customers.
- A subset of cases hand-picked from a column — works for small customers.

A good load plan respects: **block(stop k) is in the same physical location as the empties block we'll create at stop k**.

---

## Edge case: pure returns (`841...` albaranes)

The 1.296 lines with `Entrega` prefix `841...` look like **pure returns** — the customer is just clearing accumulated empties (no new product on that albarán). They're rare (1.5 % of lines) but real.

For our model we can:
- Either ignore them (volume impact is small) for the first iteration.
- Or model them as "pickup-only" stops with no outbound load — these *consume* extra space rather than swap it.

→ Tracked as Q12 in `QUESTIONS.md`.

---

## What's not in ZM040

The 45 (Material, UMA) combos in deliveries with no `ZM040` master entry are returnables:
- `CJ11V, CJ12V, CJ13, CJ13V, CJ15` — empty cases
- `BRL18V, BRL20V, BRL30V` — empty barrels
- `BT12V, BT13` — empty bottles
- `3ENV0017, 3ENV0021, 3ENV0023, 3ENV0029, 3ENV0033, 3ENV0038, 3ENV0041, 3ENV0042, 3ENV0044, 3ENV0053, 3ENV0054, 3ENV0055, 3ENV0058, 3ENV0078, 3ENV0093, 3ENV0236, 3ENV0576, 3ENV075, 3ENV1281, 3ENV1295` — individual returnable containers (cacaolat, vichy, gaseosa siphons, garrafas, etc.)
- `PL11V, PL12V` — empty plastic crates (smaller PET)

To estimate their physical volume we need a **mapping retornable → full counterpart** (CJ13 → ED13, CJ15 → ED15LN, BRL30V → ED30, …). Heuristic:

| Retornable | Full equivalent | Reason |
|---|---|---|
| `CJ13` | `ED13` | Same plastic crate, just empty |
| `CJ15` | `ED15LN` | Same |
| `CJ14` | `ED14P6` | Same |
| `CJ12V` | `VE12SP` (Veri 1/2) | Same |
| `BRL30V` | `ED30` | Same barrel |
| `BRL20V` | `TU20` | Same barrel |
| `BRL18V` | `TU18` | Same barrel |
| `PL11V` | `PL11` | Same |
| `PL12V` | `PL12` | Same |
| `3ENV0xxx` | nearest matching `0xxxxxx` family | Approximate (case standard 30×40×30 cm) |

This is in `ASSUMPTIONS.md` (A2). To validate as Q4.

---

## Why this changes the model from "VRP + bin packing" to something subtler

Standard VRP-with-3D-bin-packing assumes monotonic emptying: you load a full truck, you unload it stop by stop, you finish empty. The retornables flow breaks that — the truck **never empties** during the route, it *swaps content*.

The right framing is a **Pickup-and-Delivery Problem (PDP)** where:
- Each customer i has both a delivery quantity Dᵢ and a pickup quantity Pᵢ ≈ Dᵢ_returnable.
- Capacity constraint at any point along the route: Σ(Dⱼ for j > i) + Σ(Pⱼ for j ≤ i) ≤ truck capacity.
- The packing constraint is: Pᵢ should fit in the slot freed by Dᵢ (or a nearby slot if not exact).

This is well-studied — keywords for the research phase: **VRPSPD** (VRP with simultaneous pickup and delivery), **VRPSDP**, **VRPB** (with backhauls).
