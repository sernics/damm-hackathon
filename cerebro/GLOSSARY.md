# Glossary

Every code, abbreviation and field we ran into. Keep this open while reading anything else.

---

## Codes / IDs

| Code | Format | Meaning | Example |
|---|---|---|---|
| Cliente / Deudor | `91xxxxxxxx` (10 digits) | Customer / delivery point | `9100696143` |
| Ruta | `DR0xxx`, `DA0216`, `DR0GEN` | Route master code | `DR0027` |
| Zona | `DDxxxxxxxx` | Geographic micro-zone (cluster of nearby clients) | `DD13100043` |
| Tractor / Vehículo | `V2xxxxx` + plate | Truck unit | `V235045` / `7524KXX` |
| Repartidor | `850xxx` / `855xxx` | Driver code | `850004` (Fran Romero) |
| Transporte | 8 digits | A specific trip on a specific day | `11420136` |
| Entrega | 9 digits, prefix 827/828/841 | Albarán (delivery note) | `827937019` |
| Material / SKU | 4–7 alphanumeric chars | Product reference | `ED13`, `0CF0357`, `BRL30V` |
| Centro | `D131` | Distribution centre (Mollet = D131) | `D131` |
| Almacén | `0001`, `0005`, `0002` | Warehouse area within a centre | `0001` |
| NºCarga | 8 digits + `/D131xxxxxxx` | Load / preparation order ID | `11764300/D131999991` |
| Cl. transp. | `YT04`, etc. | Transport class | `YT04` |

---

## Albarán prefix sub-types

| Prefix | Likely role |
|---|---|
| `827...` | Delivery (cash variant?) |
| `828...` | Delivery (credit variant?) |
| `841...` | Pure return / abono (no new product, only empties) |

---

## Units of measure (UMV / UMA / UMB)

| Code | Meaning |
|---|---|
| **PAL** | Pallet (60 cases or so) |
| **CAJ** | Caja (case) — typically 24 bottles 1/3, or 12 cases of Veri… |
| **UN** | Unidad (single piece) |
| **BOT** | Botella (single bottle) |
| **BRL** | Barril (barrel: 20 L, 30 L, etc.) |
| **TB** | Tubo (CO₂ / gas cylinder) |
| **PAK** | Pack (multipack) |
| **EST** | Estuche (boxed set) |
| **PQ** | Paquete |
| **TIR** | Tira |
| **BID** | Bidón |
| **ZPR** | Promo unit |
| **ZCE / ZPM / ZS3 / Y04…** | SAP-internal extra unit codes (ratios, packs, hierarchies) |
| **L** | Litros (liquid volume) |
| **KG** | Kilos (mass) |
| **KGL** | Kilo-litro (rare) |
| **G/L**, **V%** | Density / volumetric percent |

---

## Warehouse location codes

Pattern: `[ÁREA][PASILLO][NUM][NIVEL][ALT]` — e.g. `FA05A2`.

Special values:
| Code | Meaning |
|---|---|
| `A0DISTRIDA` | Distridam zone (Damm subsidiary) |
| `ZCG` | Comergrup zone (joint distribution: cleaning, snacks, spirits) |
| `PLV` | POS / marketing material |
| `ENVASE` | Returnable empties storage |
| `AAAAAA` | Default / unassigned |

---

## SKU prefixes (rough taxonomy)

| Prefix | Family |
|---|---|
| `ED…` | Estrella Damm (product) |
| `CJ…` | Caja retornable (empty crate) |
| `VO…` | Voll-Damm |
| `FD…`, `FDT…`, `FDL…` | Free Damm range |
| `TU…` | Turia |
| `BH…` | Bohemia |
| `DL…` | Damm Lemon |
| `EC…` | Daura Damm |
| `BRL…` | Barril (BRL30 = 30L; BRL30V = empty 30L) |
| `VE…` | Aigua Veri |
| `0AG…` | Vichy / Font d'Or aguas |
| `0RF…` | Refrescos (Coca-Cola, Schweppes, Aquarius, Bitter Kas) |
| `0LT…` | Lácteos / cacaolat / Letona |
| `0CF…` | Café (Bonka) |
| `0VE…` | Vino |
| `0LI…` | Licores / spirits |
| `0AM…` | Alimentación seca (snacks, conservas, especias) |
| `0LM…` | Limpieza, menaje, consumibles |
| `0ZU…` | Zumos |
| `UE…`, `UC…` | Utensilios (vasos, copas, abridores) |
| `3ENV…` | Envase retornable individual (1/3 vidrio, etc.) |
| `PL…` / `PL…V` | Plastic crates (lleno / vacío) |
| `NTL…` | Nestea |

---

## Acronyms we use

| Term | Meaning |
|---|---|
| DDI | Distribució Directa Integral (Damm's distribution arm) |
| HORECA | Hotel / Restaurant / Cafeteria channel |
| ZM040 | The SAP report ID we read for material dimensions |
| PLV | Punto de Venta (POS marketing material) |
| LIFO | Last In, First Out (truck loading constraint) |
| VRP | Vehicle Routing Problem |
| VRPTW | VRP with Time Windows |
| VRPSPD | VRP with Simultaneous Pickup and Delivery (the framing for retornables) |
| VRPB | VRP with Backhauls |
| PDP | Pickup and Delivery Problem |
| TSP | Travelling Salesman Problem |
| 3D-BPP | Three-Dimensional Bin Packing Problem |
| WMS | Warehouse Management System |
| TMS | Transport Management System |
| OSM / OSRM / ORS | OpenStreetMap / Open Source Routing Machine / OpenRouteService |
| SAP / ERP | The internal management system DDI uses |

---

## Things named in the data that aren't documented

If you find a field, value or code not listed here, **add it**. The whole point of this glossary is to reach saturation: everything is here.

Open spots (please fill if you find out):
- `Sector` (Horarios) — code `8` is dominant, what does it mean? Likely "HORECA bars".
- `Organización ventas` — code `235` everywhere. DDI Mollet's sales org code.
- `Canal distribución` — code `1` everywhere (`Canal distrib. MARCA`).
