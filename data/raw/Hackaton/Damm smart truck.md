# Damm Smart Truck
**Damm · Interhack BCN 2026**

---

## 1. Context and Motivation

Damm is a company with a highly complex logistics operation, tied to product distribution across multiple channels and points of sale. In this context, DDI (Distribució Directa Integral) plays a key role as the group's distribution network, with a multi-product catalogue of top-tier brands and a presence across the Iberian Peninsula, the Balearic Islands, and the Canary Islands.

DDI provides agile, flexible, and personalised service to its clients, particularly in the hospitality channel. Every day, distribution teams must prepare, load, and deliver orders to different clients, with routes that can include approximately 15 to 25 deliveries per truck.

Currently, load preparation is done primarily by grouping products by reference. This model makes warehouse preparation easier and allows for better use of available truck space. However, during deliveries, the driver may need to search for products in different parts of the vehicle to complete each client's delivery — which can lead to extra movement, time losses, and unloading inefficiencies.

Furthermore, the delivery order is not fully predefined: it is often the driver who ends up deciding the route based on their knowledge of the area, the clients, and the day's conditions. This opens up an opportunity to explore how technology, data, and optimisation can help make better decisions by combining two dimensions that are usually treated separately: **the delivery route** and the **physical loading of the truck**.

The challenge must also account for DDI's operational reality: different product types and volumes, limited truck capacity, handling restrictions, lateral access to pallets via tarpaulins, client schedules or preferences, and reverse logistics. Approximately 60% of delivered products are returnable, meaning trucks also collect empty crates, containers, or barrels during the route.

This challenge is relevant because better coordination between route, loading, and operations can generate impact in terms of efficiency, delivery time, ergonomics, sustainability, service quality, and scalability of the logistics model.

---

## 2. Challenge Objective

The objective of the challenge is to design a solution that jointly optimises the delivery route and the truck's load configuration, taking into account the delivery order, product volume and type, vehicle capacity, reverse logistics, and the operational constraints of the current process.

The ideal solution should be able to propose an efficient route and, at the same time, recommend how to physically prepare the load so that unloading is more agile and consistent with the delivery order — without excessively penalising space utilisation or warehouse preparation.

Solutions will be especially valued if they combine a solid technical approach with a realistic application to Damm's logistics context. The goal is not simply to find the shortest route, but to find the best balance between **route efficiency**, **load efficiency**, **ease of unloading**, and **operational feasibility**.

---

## 3. Technical Challenge / Functional Requirements

The proposed solution should cover, at minimum, the following elements:

- **Route optimisation:** Propose a visit order for clients taking into account variables such as distance, estimated travel time, number of clients, possible time windows, delivery restrictions, or priority criteria.

- **Load optimisation:** Recommend a physical load configuration for the truck taking into account each client's products, volume, product type, vehicle capacity, and planned unloading order.

- **Balance between reference-based and client-based loading:** Explore whether it is better to maintain loading grouped by reference, switch to loading grouped by client, or propose a hybrid model that maximises overall efficiency.

- **Load visualisation:** Include a visual representation — even if simplified — of how the truck would be loaded: zones, pallets, product groups, associated clients, or recommended unloading order.

- **Reverse logistics:** Incorporate the collection of returnables as a variable in the model. The solution should consider that the truck not only delivers products, but may also be recovering empty crates, containers, or barrels during the route.

- **Real operational constraints:** Take into account that trucks have lateral tarpaulins allowing pallet access from the side, and that loading must be viable from a warehouse, handling, safety, and preparation-time perspective.

- **Warehouse layout:** Consider, as an optional variable or extension of the challenge, whether a different warehouse layout could facilitate the preparation of more efficient loads based on route, client, or product type.

- **Automatic recommendations:** Generate actionable recommendations for logistics teams, such as: best loading order, clients that should be grouped together, critical products, expected friction points, or alerts about inefficient configurations.

- **Solution explainability:** The proposal should explain why it recommends a particular route or configuration, which criteria have been prioritised, and what trade-offs it assumes between space, time, ease of unloading, and overall efficiency.

The solution can take different forms: an optimisation algorithm, a functional prototype, a simulator, a visual tool, an interactive dashboard, a recommendation model, or a combination of these elements.

---

## 4. Available Resources and Data

Damm will provide teams with contextual information and, where possible, sample or synthetic data to work on the challenge. The planned resources are:

- **Sample order and delivery data from DDI:** Examples of orders with clients, product references, quantities, formats, volumes, or approximate logistics units.

- **Examples of routes or client assignments:** Samples of how different clients may be assigned to a driver or truck for a delivery day.

- **Information about DDI's current operations:** Explanation of the current load preparation process, criteria used, limitations, and identified friction points.

- **Warehouse images or diagrams:** Visual materials to help understand how references are currently organised and how the load is prepared.

- **Truck loading images or diagrams:** Examples of how products are currently distributed inside the trucks.

- **Simplified operational constraints:** Estimated truck capacity, lateral access, product types, handling, volume or weight limitations, and basic safety considerations.

- **Reverse logistics information:** Estimated percentage of returnable products and examples of typical returns during a route.

- **Damm and DDI mentors or experts:** During the event, Damm and DDI will aim to have members of the Distribution and Data & AI teams available to answer operational and technical questions from participants.

> In cases where real data cannot be shared for confidentiality reasons, anonymised, simplified, or synthetic data will be provided that reproduces the logic of the problem.

---

## 5. Expected Deliverables

At the end of the challenge, each team must present a proposal that conveys both the technical solution and its practical application within Damm's context. The expected deliverables are:

- **Functional prototype or conceptual demo:** A tool, model, simulator, script, dashboard, or interface showing how route and load could be jointly optimised.

- **Algorithm or decision logic:** Clear explanation of the approach used: optimisation criteria, variables considered, constraints incorporated, and model priorities.

- **Solution visualisation:** Visual representation of the proposed route and the recommended truck load configuration.

- **Application to a specific use case:** A practical example with a simulated or sample route, indicating which clients are visited, in what order, how the truck is loaded, and what benefits are expected.

- **Results and expected impact:** Qualitative or quantitative estimation of the potential impact: reduced unloading time, better truck utilisation, fewer movements, fewer kilometres, better driver experience, or greater operational efficiency.

- **Final pitch:** A brief presentation covering the problem addressed, the proposed solution, assumptions used, limitations, results, and next steps to take the proposal to a real pilot.

> The solution does not need to be fully finished, but it must be understandable, defensible, and applicable to a realistic logistics scenario.

---

## 6. Evaluation Criteria

Proposals will be evaluated according to the following criteria:

| Criterion | Weight |
|---|---|
| **Real applicability to Damm's context** — Does the solution take into account real operational constraints? Is it viable in a distribution environment like Damm's? Does it properly understand the role of the warehouse, driver, loading, and unloading? | 30% |
| **Technical quality of the solution** — Is the optimisation approach solid? Are the variables well defined? Does the solution correctly combine route, load, and constraints? Is the prototype or model coherent? | 25% |
| **Potential impact** — Can the proposal generate meaningful improvements in efficiency, time, sustainability, service quality, ergonomics, or scalability? | 20% |
| **Creativity and originality** — Does the team propose a differentiated approach? Does it explore hybrid solutions, useful visualisations, intelligent recommendations, or new ways of making decisions? | 15% |
| **Clarity of communication and pitch** — Is the solution explained clearly? Are the assumptions, results, and limitations understandable? Does the pitch help envision how the proposal could be taken to practice? | 10% |

Proposals that not only optimise on paper, but also demonstrate sensitivity to the real logistics operation — warehouse preparation, truck loading, product access, driver decision-making, returnables, and the client unloading experience — will be especially valued.