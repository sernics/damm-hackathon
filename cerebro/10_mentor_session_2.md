# 10 — Mentor Session #2 Findings (2026-05-09 second meeting)

A second mentor session that corrected several model assumptions and gave us new operational structure to model. This file is the canonical log; specific deltas have been propagated to the affected modules.

> **Read with caution.** Some of the notes are paraphrased from the conversation and may be slightly imprecise. Items flagged `[CHECK]` are the ones to verify on a follow-up.

---

## Major corrections (vs. what we previously believed)

### Truck unloading is not "rear-only"

We had assumed only the rear pallet could be unloaded as a whole pallet. Mentor:

> "El palet trasero se puede descargar con los dos paletas. Y a partir que hemos descargado el trasero, si hiciera falta descargar los otros, siempre que no esté el trasero, se puede descargar."

Two implications:

1. **Pallets can move inside the truck.** The internal divisions are articulated and fold up. With a pallet jack the driver can drag a middle pallet to the rear, *if the path is clear*.
2. **Once the rear is empty, the next-to-rear becomes the rear.** Whole-pallet unloading propagates from the back of the truck.

So the right model isn't "fixed positions" but **LIFO order with a small re-shuffle budget per stop**. Position k in the truck can be unloaded as a whole pallet *if and only if* positions k+1, k+2, …, last have already been unloaded (or the partitions allow extraction laterally for that specific stop).

### Hard cap on whole-pallet stops per route

> "Lo normal es que en una ruta podamos descargar 2, a lo máximo 4 palets enteros. Más no se suele hacer."

A route can have **at most 2-4 whole-pallet customer stops** in practice. Everything else is **case-by-case**, and that's the dominant pattern. If our solver proposes 8 whole-pallet stops, it's not realistic.

### "Case-by-case is 3-4x slower" was an oversimplification

> "No es proporcional. Depende mucho. Hay clientes a pie de calle donde dejas las cajas en la entrada. Y hay otros que tendremos que andar 50 metros con la carretilla y tendremos que ir al fondo del almacén."

The real cost driver isn't the case count. It's **how far the driver has to walk inside the customer's premises** (street to delivery point). For some bars it's "leave it at the door". For some restaurants it's "down the corridor, second left, 50 m".

Implication: we need a per-customer **interior distance** variable. Without it, our unload-time estimates are wrong by a large factor at some customers. **`[CHECK]`** Is this captured anywhere in the SAP master, or do we need to crowd-source it / leave as a "to be measured" feature?

### Layout flexibility: SKU-to-location, NOT physical racks

We previously discussed "warehouse re-layout" as one of three architecture options. Mentor clarifies:

> "Podemos modificar los productos que hay en cada ubicación. Sí, pero los juegos no."

So:
- **Allowed**: re-mapping which SKU lives in which physical position (logical re-layout).
- **Not allowed**: moving the racks themselves (physical re-layout / civil works).

Implication: re-layout in our pitch means **changing the SKU-to-Ubicación mapping**, not building new racks. Cheaper, faster, more realistic.

### Picking can be split into "global + dedicated" blocks (this confirms Q4 architecture)

> "Si decidimos que un cliente lo vamos a hacer aparte, solo cargaríamos 30 cajas en el global y 10 cajas en el taller de ese cliente."

The picking process can be **split**: a global alphabetical sweep for the bulk + dedicated cart(s) for priority customers. **This is exactly the hybrid we proposed in `08_solution_sketch.md`.** It's not a moonshot — it's a small adaptation of today's flow.

### "Cases on top of barrels" is soft, not hard

> "Las cajas las pueden poner sobre los barriles. No es lo más óptimo, pero se pueden llegar a poner."

Our packer should treat this as a **penalised configuration**, not a hard constraint. Same logic likely applies to other "preferred but not forbidden" combinations.

### The pitch-defining sentence

> "Nosotros no estamos buscando lo más óptimo para repartir, sino que estamos buscando un equilibrio. Lo más óptimo posible para cargar y lo más óptimo posible para repartir."

The objective function is **explicitly joint warehouse-cost vs delivery-cost**, not delivery-cost minimization with a warehouse-feasibility constraint. If our pitch promises "30 % faster routes" but doubles picking time, **the mentor will reject it**.

### Weight is not a binding constraint

> "El peso no lo hagáis caso. Hagáis caso a las cajas."

Drop kg from the constraint set. The hard physical limit is **case count and pallet count**, not mass. (Likely because the truck's structural limit comfortably exceeds the practical case-count limit; nobody has ever hit the kg ceiling.)

---

## New operational structure that wasn't in our model

### A. The "park and walk" pattern (a clustering insight)

> "Si tengo tres clientes seguidos, a lo mejor me va mejor parar aquí y hacer este cliente, y desde aquí hacer este cliente de la punta. Y a la hora de recoger los envases, si hago los tres clientes de golpe, yo dejo el envase en la calle y cargo el envase al final de hacer los tres clientes."

For tight customer clusters (3 customers within walking distance), the driver:
1. Parks the truck once.
2. Walks to client A, delivers, *leaves the empties in the street*.
3. Walks to client B, delivers, leaves empties in the street.
4. Same for client C.
5. Collects *all the empties from the street at the end* and loads them onto the truck once.

A pure TSP/VRP cost model treats each customer as a separate truck stop. This **overestimates the time and effort** for clustered customers. Our model needs to recognise customer clusters and:
- Treat the cluster as **one truck stop** with multiple inner customer visits.
- Aggregate the empty-pickup at the *end* of the cluster, not per customer.

### B. Operating hours

- **First truck out: 6:00 AM** (hard).
- **Return: no fixed cutoff.** Varies between ~12:00 (Monday in winter) and ~19:00 (Friday in summer). Demand-driven.

So the cutoff is **soft**. Our routing solver should not reject routes for exceeding a fixed return hour. We can include it as an objective penalty (longer routes are worse) but not as a hard constraint.

### C. Driver license category is a hard assignment constraint

> "Un chofer puede llevar grande o pequeño. Pero no todos los choferes que llevan pequeño pueden llevar grande."

There's a **license-category field** in the driver master (level 1, 2, or 3 — `[CHECK]` exact values). Level 1 drivers can drive small trucks only; level 3 drivers can drive any. Our truck-to-driver assignment **cannot freely permute** — it must respect this.

### D. Driver-truck pairing is stable, not rotated

> "El repartidor nunca cambia de camión. Siempre tienes tu camión. Podría cambiar, pero lo normal es que no cambie."

Drivers don't get reassigned a different truck each day. The (driver, truck) binomial is **stable**. The traffic chief assigns a *route* to that pair, not a truck.

Implication: we model the driver-truck mapping as **fixed input**, not as a decision variable. The decision variable is which clients go on which (driver, truck) pair on a given day.

### E. Customer time windows do exist, even if not always in CSV

> "Un par a lo mejor puede abrir a las 9 y el otro está al lado de las 10."

So the 90 % of customers without explicit `Horarios_Entrega` rows still have informal opening hours. The driver knows them. Our model should at minimum **respect the 120 customers with explicit windows**, and have a default "08:00-22:00" for the rest (A13).

### F. 4 levels of cases per pallet (probable)

Mentor said "cuatro alturas normales" near the end of the call, probably meaning **4 levels (rows) of cases stacked on a pallet**. Combined with the "60 cases per pallet" rule of thumb, that suggests roughly 15 cases per level.

`[CHECK]` Confirm exact number, and whether it varies by case format (1/3 vs 1/5 vs Veri).

### G. The case is the atomic unit of modelling

> "Tú la caja se la das al cliente."

Don't model at the unit / bottle / can level. Even when selling "12 unidades sueltas", the unit moves around the warehouse and the truck inside a case. Our model operates at **case granularity**.

### H. Volume conversion: 4 cases = 1 barrel

A new rule of thumb. A 30 L barrel occupies the volumetric space of about **4 cases**. Useful for back-of-envelope capacity calcs in the pitch.

### I. The mysterious "400 son las básicas" `[CHECK]`

The mentor said something about "400 are basic". Possible interpretations:
- 400 cases is the typical "basic" transport volume.
- 400 mm is the basic case dimension.
- 400 SKUs are the "basic" set always carried.

Worth a quick clarification.

### J. The driver's only interface is the printed albarán

> "Él pilla, se sube al camión y no tiene nada, ni usa Waze ni Maps. Bueno, puede usar Maps, pero es lo que decidan. Nadie le dice qué hacer."

The driver works from the **printed albarán** — no app, no GPS routing tool by default. Implication: **our recommendation must materialise on the albarán print or the driver won't see it**. A nice mobile UI is wasted unless he chooses to use it.

### K. Veteran-vs-novice asymmetry (pitch gold)

> "Imagínate que yo me hiciera camionero, no lo sabría. Sería difícil. Cada servidor hace su ruta. Si un día no hago mi ruta porque el otro no ha venido, lo más probable es que vea el objeto y no haga otra ruta."

Drivers are optimised for **their own route**. Pull a driver onto a new route and performance plummets. Direct quote we can use in the pitch:

> *"Our tool makes any driver perform like a veteran on any route."*

This is a real pain point at DDI today (cover drivers, holiday substitutions, new hires) and our solution addresses it by externalising the heuristic.

---

## Mentor's explicit and implicit recommendations

1. **Optimise the balance, not delivery alone.** Joint objective function `(picking_cost, delivery_cost)`.
2. **Model in cases, not kg.**
3. **Picking can be split** into global + dedicated blocks today. Use it.
4. **Don't propose pure "by-customer" loading.** That's the extreme they don't want. Hybrid is the sweet spot.
5. **Respect license category** in truck-driver assignment.
6. **The driver decides ultimately.** Our output is a recommendation, not an order. Reduces organisational friction.
7. **Surface our recommendations on the printed albarán.** That's the actual UI.
8. **Capture the veteran heuristic.** Pitch headline.

---

## Yellow flags (things to revisit in our model)

| Flag | What it means |
|---|---|
| **2-4 whole-pallet stops max per route** | Our solver's pallet-tour configuration is upper-bounded by this. |
| **Customer interior distance** | New per-customer feature we don't have data for yet. |
| **Joint objective** | Re-weight `08_solution_sketch.md` cost function. |
| **License category** | Hard constraint on truck-driver assignment. |
| **Soft return cutoff** | Don't reject routes for exceeding a fixed time. |
| **Cases-on-barrels = soft** | Penalty term, not a forbidden combination. |
| **Driver-truck stable** | Treat as input, not as decision variable. |

---

## Open follow-ups arising from this session

These have been added to `QUESTIONS.md`:

- **Q43.** What are the exact license-category values (1/2/3 or other) and the truck classes they unlock? (Q33 was about external vs internal driver — different question.)
- **Q44.** Do we have access to the driver master with license category as a column?
- **Q45.** Is "client interior distance" captured anywhere — perhaps as free text in client notes? Or does the driver carry it in his head?
- **Q46.** "400 son las básicas" — what does this refer to? Cases? mm? SKUs?
- **Q47.** Is "4 levels per pallet" a universal rule or does it vary by case format (1/3 long-neck vs 1/5 vs Veri)?
- **Q48.** Are `3ENV0xxx` truly returnable or were they bundled into "cases" / not retornable? (still open from session 1)
