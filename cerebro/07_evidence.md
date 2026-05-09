# 07 — Evidence: the route↔load decoupling, in real documents

This file documents the *empirical* proof that today's process is misaligned. It comes from three real PDFs from a single transport (NºCarga 11764300, route DR0027, driver 850004 FRAN ROMERO, date 2026-05-08).

---

## Setup

| Field | Value |
|---|---|
| NºCarga | 11764300 / D131999991 |
| Route | DR0027 |
| Driver | 850004 — FRAN ROMERO |
| Vehicle | V235045 (plate 7524KXX) |
| NºViaje | 01 |
| Date | 2026-05-08 |
| Total cases on the truck | 815 |
| Total clients on the route | 18 |
| Total proforma value | 7.832,38 € |

---

## Document 1 — Hoja Carga (warehouse picker's list)

**Order:** alphabetical by warehouse `Ubicación`.

```
A0DISTRIDA   →  AA02A1  →  AA03A1  →  AA04A1  →  …
…AA11A1      →  AC01A1  →  AC03A2  →  AC03A3  →  …
…AC08A3      →  BA01A1  →  BA02A3  →  BA03A3  →  …
…BC04A3      →  CA04A2  →  CA06A2  →  CACB04A1 → CB05A3 → …
…CB06A2      →  DA07A3  →  DA09A1  →  DB04A3  →  DB06A1  →  …
…E007A1      →  EA08A1  →  EB02A1  →  EB03A1  →  …
…FA01A1      →  FA02A2  →  FA03A1  →  FA05A2  →  FA06A3  →  …
…FC02A2      →  FC04A3  →  FC05A3  →  ZCG ……
… "Carga lleno sin ubicación" (final block) …
```

This is **the picker's path through the warehouse**, optimised for warehouse traversal.

---

## Document 2 — Hoja Ruta (driver's stop list)

**Order:** geographic clusters of nearby villages.

| # | Customer | Town |
|---:|---|---|
| 1 | BAR PAVELLO ST JULIA VILATORTA | Sant Julià de Vilatorta |
| 2 | BAR EL TUPÍ | Sant Julià de Vilatorta |
| 3 | MAS L'ALBAREDA | Sant Julià de Vilatorta |
| 4 | BAR NURIA ST. JULIA VILATORTA | Sant Julià de Vilatorta |
| 5 | CAL TEIXIDOR | Sant Julià de Vilatorta |
| 6 | RESTAURANT EL ROSER | Calldetenes |
| 7 | CELLER CALLDETENES | Calldetenes |
| 8 | SUKI PA | Calldetenes |
| 9 | BAR DE LA BENZINERA (× 2) | Calldetenes |
| 10 | CAL ANENA | Calldetenes |
| 11 | BAR KARNAK | Folgueroles |
| 12 | L'ESPAI RESTAURANT | Folgueroles |
| 13 | LA COCA DE FOLGUEROLES | Folgueroles |
| 14 | CAL CISTELLER | Folgueroles |

This is **the driver's actual route**, optimised for distance.

---

## Document 3 — Albarán (delivery note for client 412 COFFEE & BEER)

A typical albarán has ~25 lines mixing:
- Cervezas retornables (FD13, FDT13, BH13P6 …) + their empty cases (CJ13).
- Barriles (ED30, TU20, VO20).
- Aguas (VE12SP, VE32SP).
- Refrescos, cafés, vinos, licores.
- Limpieza y consumibles.

A single customer's order spans **many warehouse zones** (A, B, C, D, E, F, ZCG). Therefore: in the truck right now, that customer's products are not contiguous.

---

## The mismatch quantified

Let me pull one stop (`BAR EL TUPÍ`, hypothetical based on patterns we see) and trace where its products are in the truck:
- Cerveza retornable (CAJ ED13) → loaded from `AA09A1` → ended up in the *first* part of the truck.
- Free Damm (FD13) → loaded from `AA06A1` → also early.
- Vichy retornable (`0AG0011`) → loaded from `AC07A1` → middle area.
- Veri 1/2 (`VE12SP`) → loaded from `EB03A1` → near the back/late.
- Bonka coffee (`0CF0355`) → loaded from `FC05A3` → at the very back.
- ZCG products (Comergrup) → loaded last → wherever there's room.

When the driver arrives at `BAR EL TUPÍ` (stop #2) they need to:
1. Open the side curtain at multiple points.
2. Pull the first beer crates from the front (easy).
3. Move other clients' pallets to reach the Veri at the back (hard).
4. Crawl over to ZCG (hard).
5. Hand the empty crates back into whatever spot is free.

Multiply by 18 stops with this kind of search. **That's the cost we want to eliminate.**

---

## Photo evidence supporting the mismatch

Several photos in `Fotos Mollet/` show:
- A truck loaded with **rows of identical red Estrella crates** stacked deep inside, plus **blue Veri crates** on the side, plus **Vichy/Coca-Cola crates** mixed in. The crates are grouped by brand, not by destination customer.
- One striking photo shows a **mosaic-style mixed pallet** assembled for one specific customer (Estrella + Veri + Vichy + multi-brand cases as a clean stable tower). This proves that **mixed-by-client preparation is technically feasible** — they already do it manually for some customers.

So the "hybrid model" the brief asks for already exists in artisanal form. The question is how to systematise it.

---

## What this evidence suggests for our solution

1. **The picker's sweep cannot be sacrificed completely.** The current load order (alphabetical by location) IS efficient for picking. We can't replace it with "client-by-client" without explosive picker-trip cost.
2. **A staging zone between picker and truck would solve it.** Picker drops cases into a zone organised by *destination client* (one bay per stop), which then gets loaded onto the truck in *route order*. That doubles the handling once but eliminates all the in-truck searches × 18 stops.
3. **Or: train the picker on a "lap per stop" model** with batched picks (warehouse zones → cart → pre-pallet by stop) — this is the **mosaic pallet** we already see in the photos.
4. **Or: physical re-layout** — concentrate high-frequency clients' SKUs near each other in the warehouse so a "by-client" picking sweep becomes geographically tight.

Each of these has a distinct cost / disruption profile. A good submission will compare them.
