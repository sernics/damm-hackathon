# Blocking Questions — Take These to the DDI Mentors

The 7 questions that, if unanswered, force us to either (a) invent placeholder data and downgrade the credibility of the pitch, or (b) build the wrong architecture and have to redo work.

Each one is explained in plain language, with the operational reason behind it, the cost of not having an answer, and a concrete phrasing you can literally paste in front of a mentor.

> **Status update — first mentor session (2026-05-09):** see the "Mentor responses" section right below for the per-question status. Then read each question section for the full context.

---

## Mentor responses (2026-05-09)

### Q1 — Truck dimensions: `[PARTIAL]`
No exact dimensions in meters or kg yet. But a big new operational rule emerged (see Q4) plus a pocket rule: **roughly 60 cases per pallet**. Follow-up still needed for L x W x H, max payload, double-stacking, lonas layout.

### Q2 — Visit order / Trip Priority: `[ANSWERED — and it's bad news]`
The `Nº Prioridad VIAJE` field exists but **DDI cannot expose it to us**: "that route we can't see, to compare". And literally: "we don't have any record of what the real order was that the driver followed on the route, to know how they did it." So **the historical baseline cannot be reconstructed**. The driver decides autonomously each morning based on experience. Implication: we cannot build a "today vs. optimised" comparison from real data — we have to invent a sensible baseline (e.g. naive geographic order or row-order proxy) and be transparent about it in the pitch.

### Q3 — Returnable empty vs full: `[ANSWERED]`
"Cases are stackable and occupy the same empty as full, only weigh less. Barrels too." Important clarification: **the only items that come back as returnables are glass cases and barrels**. Cans, cleaning products, spirits — NOT returnable. This conflicts with our hypothesis about the `3ENV0xxx` SKUs (which we tagged as returnable individual containers): either the mentor simplified or those `3ENV0xxx` items are bundled inside "glass cases" in their head. **Mandatory follow-up question** (added to QUESTIONS.md).

### Q4 — Picking flexibility: `[ANSWERED — opens the door]`
Today the alphabetical-by-`Ubicación` order is mandatory because "we've optimised for the warehouse type, not for the driver". **But**: "the warehouse layout can be deconfigured to make it a bit more efficient." The mentor himself proposes an idea: **dedicated pallets for big, geographically close customers** ("a 30-case client and a 20-case client near each other -> you can make one pallet just with that"). So our Option 1 (staging zone) and Option 3 (partial re-layout / dedicated pallets) are on the table. Option 2 (one walk per customer) is implicitly off the table.

### Q5 — Truck/route mapping: `[PARTIAL — with one important correction]`
A driver does **1–2 transports per day, NOT 9** — corrects our previous assumption (the data quirk we observed must be edge cases, abonos or data noise). **9–20 customers per transport.** If a driver does two transports in a day, they reload the same truck. Very revealing: **the truck-to-route assignment is done manually by the traffic chief, no tool**. That's a *separate* optimisation opportunity worth surfacing in the pitch. Still no confirmation whether a vehicle-to-route master exists in SAP.

### Q6 — Time benchmarks: `[PARTIAL]`
- **Picking time: 50–60 min per truck (6 or 8 pallets).**
- **Unloading time: roughly 1.5x the loading time in the worst case, depends heavily on the client.**
- No SAP timestamps available.
- Useful free insight: **warehouse operators are different staff from truck drivers** — picking and driving run in parallel, not sequentially. This relaxes the "cut-off" constraint a lot: the driver doesn't wait for picking, picking doesn't wait for the driver.

### Q7 — Compatibility rules: `[ANSWERED LIGHTLY]`
"The warehouse order is already thought for that — I don't put a barrel on top of napkins." Mentor essentially says don't worry, the compatibility constraints are already absorbed into where each SKU lives in the warehouse. Thin if we want a rigorous list, but enough to defend in the pitch by citing it.

---

## Implications for our plan (deltas after this session)

1. **Baseline strategy changes** (driven by Q2). We can't compare against "today's actual route" because no record exists. Instead we will:
   - Use a synthetic "naive geographic" baseline (TSP shortest-distance ignoring time windows and load) as the "today-equivalent".
   - Use the row-order in `Detalle_entrega.csv` as a *secondary* proxy and explicitly flag it as "what looks like the historical SAP-suggested order, but operations confirms it's not measured."
   - Make the absence-of-baseline a *talking point* in the pitch — "we discovered DDI doesn't currently track real visit order, so step one of impact measurement is putting that telemetry in place."
2. **Architecture decision** (driven by Q4). We commit to a hybrid: the picker keeps a single sweep but drops into a small set of staging bays (one per "delivery cluster"), and we promote big-and-close customers into **dedicated mixed pallets** following the mentor's own suggestion. This is exactly the "mosaic pre-pallet" pattern visible in the warehouse photos.
3. **Returnables model simplification** (driven by Q3). For the volume-balance computation, treat *only glass cases and barrels* as returnables. Re-classify our `3ENV0xxx` mapping as "to confirm". `0LM*` (cleaning), `0LI*` (spirits), `0CF*` (coffee), latas — all one-way.
4. **Cut-off constraint relaxes** (driven by Q6). With 50–60 min picking running in parallel to driving, we don't need to model a hard "be done by X" cut-off in the routing solver — the dispatch-end timestamp is bounded by truck volume × stop count, not by warehouse capacity.
5. **New optimisation opportunity to surface in the pitch** (driven by Q5). The manual truck-to-route assignment by the traffic chief is itself an optimisation we can demo as a "for free" extension — a small assignment problem on top of our routing+packing model. Cheap to add, big visible impact.
6. **Q1 still partly blocking**. We can keep building with the placeholder dimensions, but we want a 5-min follow-up call with anyone who knows the trucks to lock in cargo box dimensions before the pitch.

---

---

## 1. Internal dimensions and rules for each truck type

### What we're asking

Mollet operates 11 trucks of 6 pallets, 4 trucks of 8 pallets, and 1 van of 3 pallets. For each of those three types we need:
- Internal **length x width x height** of the cargo box, in meters.
- **Maximum payload** in kg.
- Whether **two pallets can be stacked vertically** inside the box (one pallet on top of another) or whether stacking is only allowed for cases on top of a single pallet base.
- Layout of the **lateral tarpaulins** (lonas): how many sliding sections per side, and roughly how wide each section is.

### Why we need it

The packing plan is a 3D problem. We have to place pallets and case stacks inside a box; we cannot do that without knowing the box's actual dimensions. Worse, "double-stack pallet on pallet" doubles the truck's effective volume. If we assume single-layer when it's actually double, half our routes will look infeasible by volume and we'll route them onto the wrong vehicle. If we assume double when it's actually single, we'll propose plans that crush the bottom pallet under the top one.

The lateral tarpaulin layout matters because the driver opens curtains *in segments*. If the curtain has 3 segments and one stop's products are spread across all 3, the driver has to open 3 panels at every stop — slower and more exposed to weather/theft. We want to align customer blocks with curtain segments, but we can't if we don't know how many segments there are.

### Cost of not having it

We use the placeholders in `05_fleet.md` (educated guesses based on European medium-duty trucks). Anything we ship is "subject to confirmation of actual cargo-box dimensions" — and if asked about a specific truck during the pitch, we have to admit we don't know.

### Concrete ask to the mentor

> "For your trucks at Mollet — the 6-pallet, 8-pallet and 3-pallet — could you give us the internal cargo box dimensions (length, width, height in m), max payload in kg, and tell us whether two pallets can be stacked vertically? Also, how many sliding curtain segments are there per side, and how wide are they?"

---

## 2. The "Nº Prioridad VIAJE" field, or confirmation that CSV row order = real visit order

### What we're asking

Inside SAP, every (client, transport) assignment carries a numeric field called **`Nº Prioridad VIAJE`** — the suggested visit order within a route. The system has it. We don't see it in the CSVs we received.

We need either:
- The `Nº Prioridad VIAJE` exposed as a column in `Detalle_entrega.csv` (or a one-shot dump), OR
- A confirmation from someone in operations that "the order in which lines appear in this file is the actual order in which the driver delivered."

### Why we need it

To prove that our optimised solution is *better*, we need a baseline to compare against — i.e. *what does the driver do today*. If we can't reconstruct today's visit order, we have nothing to compare to. We've inferred from the data that the row order in `Detalle_entrega.csv` looks geographically sensible (zones progress monotonically across stops in the transports we tested), but that's a hypothesis. If it turns out the row order is just `ORDER BY` on some SAP transaction and not the real visit order, we are comparing our optimum against a fiction.

### Cost of not having it

Two options, both bad. Option A: we pretend our hypothesis is right and a critical mentor will catch us at the pitch. Option B: we benchmark against a "purely geographic order" generated synthetically from coordinates — defensible, but it's a strawman, not the real process.

The whole "applicability to Damm's reality" criterion (30 % of the score) leans on us understanding what they do today. If we can't even describe today's visit order, that section of the pitch is weak.

### Concrete ask to the mentor

> "We need to know what visit order each transport followed historically. Two questions: (1) Is the `Nº Prioridad VIAJE` field stored at line level — could we get it as a column on the `Detalle_entrega` data? (2) If not, is the order of rows in `Detalle_entrega.csv` the actual delivery order, or is it just SAP's default sorting?"

---

## 3. Whether an empty returnable occupies the same physical space as the full one

### What we're asking

Around 60 % of what's delivered comes back as a returnable: empty plastic crates (`CJ13`, `CJ15`, …), empty stainless barrels (`BRL30V`, `BRL20V`, …), empty individual containers (`3ENV0xxx`). 45 of these returnable SKUs have no entry in the dimensional master `ZM040`. We need to know whether they occupy the same outer dimensions and roughly what they weigh empty.

Specifically:
- Does an empty `BRL30V` (30 L barrel, returned) take up the same outer footprint as `ED30` (the full barrel)?
- Does an empty `CJ13` plastic crate occupy the same outer space as a full case of `ED13`?
- Do `3ENV0xxx` (individual returnable bottles / glass containers) come back stacked, palletised, in trays?

### Why we need it

The truck **does not empty during the route**. It swaps full → empty at every stop. If full and empty take up the same space, the swap is volume-neutral and we can treat each customer's slot as "delivered out, empties back in" — clean. If empties nest more compactly (e.g. 3 empty crates stack in the space of 2 full ones), then the truck has growing free space which we can use for something else.

This is the heart of the reverse-logistics part of the challenge. Without knowing the answer, we can't accurately compute the truck's available space at any point along the route.

### Cost of not having it

We use the heuristic in `06_returnables.md`: empty = same volume as full. It's probably correct for crates and barrels (same physical container). Less sure for `3ENV0xxx` (individual returnables). If we're wrong, our space calculation is off by some fraction of the route.

### Concrete ask to the mentor

> "When a customer returns empties — empty barrels, empty plastic crates, empty individual containers — do they take up the same physical space as the corresponding full units? Are 3ENV0xxx returnables (the small individual containers) palletised on the way back or loose? And roughly what does an empty 30 L barrel weigh?"

---

## 4. How flexible is warehouse picking?

### What we're asking

Today, when a transport is prepared, a worker (the picker) walks the warehouse with a forklift, picking products **in alphabetical order of warehouse location**. That's why the `Hoja Carga` (loading sheet) is sorted by `Ubicación` (`AA02A1 → AA03A1 → AA04A1 → … → ZCG`). The advantage is that it's exactly **one** walk through the warehouse. The drawback is that the truck ends up loaded by reference (all Estrellas together, all barrels together), not by customer — which is exactly the problem this hackathon is trying to solve.

The question is: how much room do we have to change this picking flow? Three plausible alternatives:
1. **Multi-bay picking + staging zone**: picker still does one alphabetical sweep, but drops cases into N staging bays (one per customer) instead of into the truck directly. Staff then load each bay onto the truck in route order.
2. **Picking cart per customer**: picker takes 18 carts (one per customer), walks the warehouse 18 times, drops each cart into the truck in route order. One walk per customer.
3. **Warehouse re-layout**: rearrange the warehouse so high-frequency customers' SKUs end up close to each other geographically. Pick by customer becomes a short walk.

### Why we need it

Each of those three options has wildly different cost / disruption / implementation timeline:
- **Option 1** (staging zone) needs floor space and an extra staff handover. Doable in weeks.
- **Option 2** (cart per customer) needs no infrastructure but multiplies picker time by ~ 5–10 ×. Probably unacceptable.
- **Option 3** (re-layout) is a multi-month project. Lots of pain, lots of payoff.

Our entire architectural recommendation depends on which of these the mentor considers realistic. If we design for option 1 and they say "no, the staging zone is full of returnables we can't move", we redesign. If we design for option 3 and they say "we can't restructure the warehouse for years", same thing.

### Cost of not having it

We have to describe all three options in the pitch as a decision matrix and let DDI choose. That's defensible but it dilutes our recommendation — we look like we're hedging instead of committing.

### Concrete ask to the mentor

> "Today the picker walks the warehouse alphabetically by `Ubicación` and drops everything into the truck in that order. To get the truck loaded by customer instead, we'd need either a staging zone between picker and truck, or a picker doing one trip per customer (much slower), or a redesign of the warehouse layout. Which of these is operationally feasible at Mollet?"

---

## 5. Mapping between physical truck and route

### What we're asking

The CSVs we have don't include a column saying *which truck did which transport*. The PDFs show one example pairing (NºCarga 11764300 was vehicle V235045 / plate 7524KXX, route DR0027). We need a master that gives us:
- Vehicle (3P / 6P / 8P) per transport (or per route).
- And, since drivers do up to 9 transports per day, whether the same truck is reused across consecutive transports of the same driver.

### Why we need it

To verify that a transport is feasible we have to compare its volume / weight against the assigned truck's capacity. If we don't know the truck, we either over-promise (load > capacity → infeasible in real life, looks bad in pitch) or under-promise (we forced it onto the bigger truck "just in case", wasting opportunity).

Routing also depends on it: a 3P van fits in narrow city streets that an 8P truck can't reach. If we don't know which truck does each route, our route distances are wrong.

### Cost of not having it

We assign trucks heuristically: route's typical volume in m³ → smallest truck that fits → done. Defensible, but if the heuristic disagrees with the real assignment in a specific case, we look uninformed.

### Concrete ask to the mentor

> "Is there a master that links each route (or each transport) to the specific vehicle that ran it — including the type (3-pallet van, 6-pallet truck, 8-pallet truck)? And when a driver does multiple transports in one day, does the truck change between them?"

---

## 6. Time benchmarks (or, ideally, raw SAP timestamps)

### What we're asking

To quantify the expected impact of the solution, we need rough numbers for:
- **Picking time**: how long it takes to prepare one transport at the warehouse (in minutes).
- **Unload time per stop**: how long the driver spends at a customer (large stop vs. small stop).
- **Travel time** within a zone vs. between zones.
- **Cut-off time**: at what time the truck must be back at base.

The much better alternative: **the SAP transport-lifecycle timestamps**. SAP records 6 timestamps per transport — `Register`, `Load start`, `Load end`, `Dispatch`, `Transport start`, `Transport end`. With those for, say, 50–100 historical transports we can compute all of the above empirically and don't have to ask anyone for benchmarks.

### Why we need it

Our pitch needs a number. "We save 12 % of unload time" or "we cut 3 km per route" sound concrete and credible. "We save approximately some minutes" sounds amateur. The 20 % of the score for *potential impact* hinges on this.

### Cost of not having it

We make estimates from analogous industries (typical HORECA delivery is 10 min per stop, etc.) and quote them with a "subject to validation with DDI's actual times". The pitch is still defensible, but it's clearly a model run on assumed inputs rather than your data.

### Concrete ask to the mentor

> "For our impact estimates we'd love rough averages: how long does picking a transport take, what's the typical unload time per stop, how long is a route from leaving Mollet to coming back? Better yet: would it be possible to get the SAP timestamps `Register / Load start / Load end / Dispatch / Transport start / Transport end` for some historical transports — say a sample of 50–100 days? With those we can compute everything ourselves."

---

## 7. Hard rules of product compatibility and load safety

### What we're asking

The driver and warehouse staff have a tacit set of rules about what can or cannot be next to or on top of what — refined over years of cracked bottles, crushed cases and unstable loads. We need them written down. Concretely:
- Can fragile glass (retornable bottles) be stacked under barrels (the 30 L barrels weigh ~ 30 kg each)? Or always glass on top, barrels on the floor?
- Are cleaning chemicals required to be physically separated from food and drink (regulation or DDI policy)?
- Pressurised cans (cerveza en lata, refrescos) under or over retornable glass — any rule?
- The cold-chain SKUs (`Ubic. = CAMARA`, e.g. `CACAOLAT MINIBRIK`) — do they need an insulated container inside the truck, or do they just travel ambient and accept some cold-chain break?
- Centre of gravity: is there a written rule (heavies in front, fragiles in back, distribute weight side-to-side) or is it just the driver's intuition?

### Why we need it

Without these rules our packing plans will look mechanically correct but operationally amateurish. An experienced loader looking at our visual will say "you can't put that there — it'll crack" and the entire 30 % of the score for *applicability* drops. With them, we hard-code them as constraints in the packer and our outputs are self-evidently sane.

### Cost of not having it

We bake in the obvious ones (heavies on the floor, fragiles on top, no chemicals near food) and flag the rest as "to be confirmed". The mentor may catch a missing rule at the pitch.

### Concrete ask to the mentor

> "What are the hard rules of how things must or must not be loaded together? Specifically: can glass be under barrels, can cleaning chemicals share space with food and beverage, are cold-chain items handled differently in the truck, and is there a written rule about weight distribution / centre of gravity?"

---

## How to use this document

Take it to the next mentor session at Damm/DDI. Print it or send it ahead. The seven questions in this order maximise unblocking value: 1, 2, 5 unlock the modelling; 3, 4 unlock the algorithm choice; 6, 7 unlock the pitch credibility.

If only one mentor session is possible, the priority order is:

> **Q4 (picking flexibility) > Q1 (truck dimensions) > Q2 (visit order / Trip Priority) > Q6 (timestamps) > Q3 (returnable equivalence) > Q5 (vehicle mapping) > Q7 (compatibility rules).**

Why Q4 first: it determines the entire architecture. Get that and we can start designing properly while the others are answered asynchronously.
