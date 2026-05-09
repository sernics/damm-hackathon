# 02 — Data Model

How the entities relate to each other in DDI's SAP/ERP, and how they map to the CSV columns we received.

---

## Code system

| Entity | Code prefix / format | Cardinality in our data | Description |
|---|---|---:|---|
| **Client** | `91...` (10 digits) | 1.203 | Delivery point: bar, restaurant, hotel |
| **Customer name** | free text | 1.184 | Same client may show two names (legal vs. trade) |
| **Zone** | `DD13100xxx` | 56 distinct in deliveries | Geographic micro-cluster (a few streets / a village). Each client is assigned to one zone |
| **Delivery zone "name"** | free text | 56 | E.g. `MOLLET CAN BORRELL`, `MOLLET BARRI OLIVA`, `BELLAVISTA`, `FOLGUEROLES` |
| **Route** | `DR0xxx` (also `DR0GEN` generic, `DA0216` coffee-only) | 24 in master, 18 active | A set of zones permanently assigned to a driver |
| **Driver (route)** | `850xxx` / `855xxx` (6 digits) | 18 active | Person assigned to drive the route |
| **Driver (internal)** | `85xx` (different from above) | — | Internal staff handling the client at the warehouse |
| **Tractor / Vehicle** | `V2xxxxx` (e.g. V235045) + plate (e.g. 7524KXX) | unknown | The truck itself |
| **Transport** | `1142xxxx`–`117xxxxx` (8 digits) | 889 | A single trip = one truck + one driver + one day + one route |
| **Delivery (albarán)** | `82xxxxxxxx` / `84xxxxxxxx` (9 digits) | 8.927 | One delivery note to one client on one day |
| **Material (SKU)** | 7 alphanumeric chars (`ED13`, `0CF0357`, `BRL30V`) | 1.489 distinct used | Product reference |

### Albarán prefix sub-types (observed empirically)

| Prefix | Lines | Likely meaning |
|---|---:|---|
| `827...` | 18.203 | Delivery, possibly cash-on-delivery |
| `828...` | 63.350 | Delivery, possibly credit |
| `841...` | 1.296 | Pure return / abono (returnables only, no new product) |

> Confirmed via top-line analysis: 841-prefix lines contain almost exclusively retornable items (CJ13, BRL*V, 3ENV*, CC*) and have no full products. To validate as Q12.

---

## Hierarchy

```
DR Route (DR0027)
  ├── owned by a driver (850004 FRAN ROMERO)
  ├── runs on a tractor (V235045 / 7524KXX)
  └── covers several zones (DD13100xxx)
         └── which contain several clients (91xxxxxxxx)
                └── each receives 1+ deliveries (Entrega 82xxxxxxxx)
                       └── each delivery has multiple lines (Material × Cantidad × UMV)

Transport (11764300) = the realisation of a route on a specific day = one DR + one driver + one tractor + one date + N deliveries

Each Transport produces:
  - 1 Hoja de Ruta (driver's stop list)
  - 1 Hoja de Carga (warehouse picker's list)
  - N Albaranes (one per delivery, given to the customer)
```

---

## Key field: Trip Priority Number ("Nº Prioridad VIAJE")

This deserves a section of its own.

The internal SAP system stores, for every (client × route × transport) assignment, a **Nº Prioridad VIAJE**: the suggested visit order within the route. The presentation we received explicitly lists it among the client-side data fields.

We **do not yet have this field** in the CSVs we were given. If we can get it, it will:
- Provide a baseline ordering to compare our optimised route against.
- Encode a lot of the driver's tacit knowledge already (since drivers presumably tweak it based on experience).
- Reveal whether the row order in `Detalle_entrega.csv` reflects this priority field (hypothesis: yes — see `ASSUMPTIONS.md` A1).

→ Tracked as **Q3** in `QUESTIONS.md`.

---

## SAP fields we should be aware of

These appear in screenshots of the internal "Modify Transport" and "Expedition Monitor" screens. Even if not in our CSVs, they shape what's *possible* with the system.

### Expedition monitor

| Field | Meaning |
|---|---|
| `PtPlaTrnsp` | Transport platform / dispatch point |
| `InPlanCarg` | Load plan ID |
| `Cl.transp.` | Transport class (e.g. `YT04`) |
| `Ruta` | Assigned route (`DR0...`) |
| `AgServTr` | Transport service agent (carrier code) |
| `Nº Transporte` | Transport number |
| `Prop` | Properties |
| `Entr.` | Number of deliveries |
| `Caja Est.` | Standard cases count |
| `T.Barriles` | Total barrels |
| `TotCajaRet` | Total returnable cases |
| `CajaSnRet` | Non-returnable cases |
| `SM Status` | Workflow status |

Implication: the system **already aggregates** the load by `Caja Est. / T.Barriles / TotCajaRet / CajaSnRet`. These four buckets are the operationally relevant categories and a sensible coarse axis for our packing model.

### Modify transport screen

Dates captured in the lifecycle of a transport:

```
Register   → Load start → Load end → Dispatch → Transport start → Transport end
```

Each transition has a timestamp. If we get historical data with these timestamps, we can compute:
- Picking time = `Load end - Load start`.
- Driver waiting time = `Dispatch - Load end`.
- Trip duration = `Transport end - Transport start`.

→ This is what we'd need to answer Q6 ("how long does each step take?").

---

## Operational rule (important)

> "Si se debe modificar un transporte siempre debe hacerse antes de Liquidarlo."

A transport can be modified up until it is *liquidated* (closed out). After liquidation it is frozen. **Implication for our model**: any "smart truck" recommendation has to be issued *before* warehouse picking starts (or at least before the truck dispatch), otherwise it is non-actionable.

> "No es necesario que todos los repartidores tengan DR."

Some drivers operate without a permanent DR assignment. Probably ad-hoc / café-only / replacement runs. Negligible for the main optimisation but explains some edge cases in the data (the `DR0GEN` generic warehouse route, the `DA0216` coffee-only route).

---

## Mapping CSV columns → entities

### `Detalle_entrega.csv` (the central table)
- `FECHA` → date of the transport (DD/MM/YYYY).
- `Transporte` → transport number.
- `Ruta` → DR route code.
- `Repartidor` → driver code (85xxxx).
- `Destinatario mcía.` (col-1) → driver name (yes, mis-named — beware).
- `Entrega` → albarán number.
- `Destinatario mcía..1` → client code (91xxxxxxxx).
- `Material`, `Denominación`, `Cantidad entrega`, `Un.medida venta` → line content.
- `Nombre 1`, `Nombre 2`, `Calle`, `CP`, `Población` → client address.
- `ZonaTransp`, `ZonaTransp.1` → transport zone (`DD13100xxx`) and its name.

> **Caveat:** the column name `Destinatario mcía.` is reused twice with different meanings (driver name vs. client code). When parsing, treat `Destinatario mcía.` as the *driver* in `Detalle_entrega` and the *client code* in `Cabecera_Transporte`.

### `Cabecera_Transporte.csv`
- One row per delivery (8.927 rows total).
- Sub-columns: `Entrega, Nº Transporte., Creado el, Repartidor, Destinatario mcía., Destinatario mcía..1`.
- Joinable to `Detalle_entrega.Entrega`. Contains no information not already available there.

### `Direcciones.csv`
- Master of clients with addresses. Joinable on `Cliente = Destinatario mcía..1`. 1.368 clients (vs. 1.203 in deliveries — some clients in master are dormant).

### `Materiales_zubic.csv`
- Master of materials with **warehouse location** (`Ubic.`). Joinable on `Material`. 1.489 materials, every single one used in a delivery has a row.

### `ZONAS.csv`
- Mapping zone → route. Useful to confirm a client/zone belongs to a given route.

### `Horarios_Entrega/Sheet1.csv`
- Per-client weekly time windows. Only 240 of 1.203 clients are listed. Joinable on `Deudor = client code`.

### `ZM040/Sheet1.csv`
- Material master with multi-UMA dimensional data (PAL / CAJ / UN / BOT / BRL / …). 7.478 SKUs (whole Damm catalogue), of which 1.444 are present in our deliveries. The remaining 45 SKUs in deliveries are returnables not catalogued (CJ13, CJ15, BRL30V, 3ENV*…) — see `06_returnables.md`.

### `Layout_Mollet/*.xlsx`
- The visual warehouse map. The CSV exports lose the colour information (which encodes zones); read the `.xlsx` directly with openpyxl.
