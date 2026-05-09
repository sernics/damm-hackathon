# 01 — Executive Context

The 5-minute version of everything. If you only read one file, read this one.

---

## The challenge in one sentence

Co-optimise **delivery route** and **physical truck load** for DDI (Damm's distribution arm) so that the order in which the truck is filled matches the order in which it is emptied — without making warehouse preparation a nightmare and respecting that ~60 % of what's delivered is returned (empty crates, barrels, containers).

---

## The scale

DDI operates **253 commercial routes**, **33 distribution centres** and **470 vehicles** across Spain (mainland + Balearic + Canary Islands). The data we have covers a **single centre, Mollet del Vallès** (Catalonia), with **18 active routes** out of 24 mapped, served by **16 vehicles**.

| Magnitude | Value |
|---|---|
| DDI routes total | 253 |
| DDI centres | 33 |
| DDI vehicles | 470 |
| Channel | HORECA (bars, restaurants, hotels) |
| Geography of available data | Vallès Oriental + Osona (Catalonia) |
| Deliveries per truck per day | 15-25 (brief), up to 32 in the data |

---

## The central operational conflict

| Today | Consequence |
|---|---|
| **Load prepared by reference** (all Estrellas together, all barrels together…) | Efficient for the warehouse picker; inefficient for the driver |
| **Route decided by the driver** on the fly, using experience | No synchrony between loading order and unloading order |
| **~60 % of delivered units are returnable** | The truck's available space changes stop by stop |

These two processes (warehouse efficiency vs. delivery efficiency) live in tension and have **never been jointly optimised**. That is precisely the gap this challenge asks us to close.

> Possibly the answer isn't either extreme, but a hybrid model.
> *— Damm public presentation, slide 6*

---

## Documentary proof of the disconnect

Two real PDFs from the same trip (NºCarga 11764300, route DR0027, driver 850004 FRAN ROMERO, date 2026-05-08):

- **Hoja Carga (loading sheet)** lists 815 items in **alphabetical order of warehouse location** (A0DISTRIDA → AA02A1 → AA03A1 → … → BA01A1 → … → CA04A2 → … → DA07A3 → … → EA08A1 → … → FA01A1 → … → ZCG). This is the picker's path through the warehouse.
- **Hoja Ruta (route sheet)** lists 18 customers in **geographic clusters**: 5 in Sant Julià de Vilatorta → 5 in Calldetenes → 4 in Folgueroles. This is the driver's actual route.

The two orderings are unrelated. When the driver opens the truck at the first stop in Sant Julià, the products for that customer are scattered across many warehouse zones because the truck was filled following the warehouse's logic, not the route's logic. → See `07_evidence.md` for the full breakdown.

---

## What the system already provides (vs. what it doesn't)

The internal SAP/ERP **does** track:
- **Trip Priority Number** (`Nº Prioridad VIAJE`) — a numeric field on the client's transport-priority assignment that gives a *suggested* visit order within the route. Whether it is followed today is unclear; whether it is well-tuned is unclear too.
- Route → zones → clients hierarchy (DR / DD / 91 codes).
- Transport class (`Cl.transp.` e.g. YT04), full lifecycle timestamps, and counters for `Caja Est`, `T.Barriles`, `TotCajaRet`, `CajaSnRet`.

The internal SAP/ERP **does not** track:
- The *actual* visit order followed (only the suggested one).
- The geographic coordinates of clients.
- Truck-internal positions of pallets at any given moment.

So we need to bring in: geocoding, a routing solver, and a load-plan model.

---

## What we want and what we don't

**Wanted (slide 12 of the public presentation):**
1. Which client order to recommend.
2. How to load the truck.
3. Which loading model to use (reference / client / hybrid).
4. How to visualise it.
5. Which recommendations to give.
6. What impact it would have.

**Not wanted (slide 11):**
1. Just a Google Maps clone.
2. A perfect Tetris-style 3D-bin-packer with no operational sense.
3. Just the shortest route.
4. Just the maximum-space solution.
5. Anything impossible to operate.

---

## Why this matters

Better coordination between route, loading and operations creates impact in:
- **Time** (warehouse preparation, truck loading, customer unloading).
- **Kilometres** (fuel, emissions).
- **Ergonomics** (driver back-pain, search time at each stop).
- **Service** (right product to the right customer at the right time).
- **Scalability** (the same model can be replicated to the other 32 DDI centres).

This is **applied AI / data on a physical operation that happens every day**, not a theoretical paper.

---

## Where the solution must land

A workable hybrid: route order respects geography and time windows; load is built so that **each customer's products are reachable when their stop arrives**; warehouse picking remains feasible (no extreme picker-trip explosion); returnables fit back in the freed space; the driver and warehouse worker can still understand and override what the system proposes.
