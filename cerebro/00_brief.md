# 00 — Challenge Brief (canonical, English)

> Source: official `Damm smart truck.md` + the Interhack BCN 2026 challenges PDF.
> Same text from both sources, consolidated here to be the single source of truth.

---

## Context

DDI (Distribució Directa Integral) is the distribution network of the Damm group. It operates with a multi-product catalogue of top-tier brands, covering the Iberian Peninsula, the Balearic Islands, and the Canary Islands. The primary channel is hospitality (bars, restaurants, hotels).

Every day, distribution teams prepare, load, and deliver orders to different clients, with routes of approximately **15 to 25 deliveries per truck**.

### Current problems

1. **Loading by product reference.** The truck is loaded by grouping products by type. This makes warehouse preparation easier, but makes unloading harder — the driver has to search for products in different parts of the vehicle to complete each delivery.
2. **Route decided by the driver.** The delivery order is not fully predefined. The driver decides based on experience, knowledge of the area, and the day's conditions.
3. **Returnables.** ~60 % of delivered products are returnable. Trucks collect empty crates, containers and barrels during the route, which changes the available space stop by stop.
4. **Lateral access.** Trucks have lateral tarpaulins (lonas) allowing pallet access from the sides, not just from the rear.

---

## Challenge objective

Design a solution that **jointly optimises**:
- The **delivery route** (visit order)
- The **physical load configuration** of the truck (what goes where)

Considering delivery order, product volume and type, vehicle capacity, reverse logistics, and operational constraints.

> The goal is **NOT** simply the shortest route. It's the best balance between route efficiency, load efficiency, ease of unloading, and operational feasibility.

---

## Functional requirements

### Mandatory

1. **Route optimisation:** propose a visit order considering distance, estimated travel time, number of clients, possible time windows, delivery restrictions and priority criteria.
2. **Load optimisation:** recommend a physical load configuration considering each client's products, volume, product type, vehicle capacity, and planned unloading order.
3. **Reference vs. client loading balance:** explore whether it's better to keep loading grouped by reference, switch to loading grouped by client, or propose a hybrid model that maximises overall efficiency.
4. **Load visualisation:** visual representation (even if simplified) of how the truck would be loaded — zones, pallets, product groups, associated clients, recommended unloading order.
5. **Reverse logistics:** incorporate the collection of returnables as a variable in the model. The truck both delivers and picks up.
6. **Real operational constraints:** lateral tarpaulins, viability from warehouse perspective, handling, safety, preparation time.

### Optional (valued)

7. **Warehouse layout:** consider whether a different warehouse layout could facilitate more efficient load preparation.
8. **Automatic recommendations:** generate actionable recommendations — best loading order, clients to group together, critical products, expected friction points, alerts about inefficient configurations.
9. **Explainability:** the solution should explain *why* it recommends a particular route or configuration, which criteria have been prioritised, and what trade-offs it assumes.

---

## Expected deliverables

1. **Functional prototype or conceptual demo** — tool, model, simulator, script, dashboard, or interface.
2. **Algorithm or decision logic** — clear explanation of the approach.
3. **Visualisation** — proposed route + recommended truck load configuration.
4. **Applied use case** — practical example with a simulated or sample route.
5. **Results and expected impact** — qualitative or quantitative estimation.
6. **Final pitch** — brief presentation covering problem, solution, assumptions, limitations, results, and next steps.

> The solution does not need to be fully finished, but it must be understandable, defensible, and applicable to a realistic logistics scenario.

---

## Evaluation criteria

| Criterion | Weight |
|---|---:|
| **Real applicability to Damm's context** — does it consider real operational constraints? Is it viable? Does it understand the role of warehouse, driver, loading and unloading? | **30 %** |
| **Technical quality** — is the optimisation approach solid? Are variables well defined? Does it correctly combine route + load + constraints? | 25 % |
| **Potential impact** — meaningful improvements in efficiency, time, sustainability, service quality, ergonomics, scalability? | 20 % |
| **Creativity and originality** — differentiated approach? Hybrid solutions, useful visualisations, intelligent recommendations? | 15 % |
| **Communication clarity and pitch** — well explained, assumptions and limitations clear, can you envision taking it to practice? | 10 % |

### What they value most

Proposals that demonstrate sensitivity to the **real logistics operation**: warehouse preparation, truck loading, product access, driver decision-making, returnables, and the client unloading experience.

### What they explicitly **don't** want

(From slide 11 of the public challenge presentation, 2026-05-06.)

> "It's not about… making a Google Maps. Making a perfect Tetris. Finding the shortest route. Just maximising space. Or building an impossible-to-operate solution."

**A simple but applicable solution can be worth more than a perfect one on paper.**
