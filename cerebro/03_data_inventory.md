# 03 — Data Inventory

Everything we have, in one place, with row counts and the numbers that matter.

---

## 1. Source files

### CSVs (already extracted)

| Path | Rows | Cols | What it is |
|---|---:|---:|---|
| `data/csv/Hackaton/Cabecera_Transporte.csv` | 8.927 | 8 | One row per delivery: Entrega, Transporte, Date, Driver, Client |
| `data/csv/Hackaton/Detalle_entrega.csv` | **82.849** | 19 | **The core table.** One row per albarán line. Material × qty × UMV × full client info |
| `data/csv/Hackaton/Direcciones.csv` | 1.368 | 6 | Client master with address |
| `data/csv/Hackaton/Materiales_zubic.csv` | 1.489 | 8 | Material master with **warehouse location** |
| `data/csv/Hackaton/ZONAS.csv` | 1.203 | 14 | Client → ZonaTransp → DR Route mapping |
| `data/csv/Horarios_Entrega/Sheet1.csv` | 1.015 | 13 | Per-client time windows (only 240 of 1.203 clients) |
| `data/csv/ZM040/Sheet1.csv` | 48.457 | 22 | Material master with dimensions / volumes / weight |
| `data/csv/Layout_Mollet/*.csv` | – | – | Layout (CSV broken — read XLSX directly) |

### Raw documents

- `data/raw/Hackaton/Damm smart truck.md` — official challenge brief (English).
- `data/raw/Hackaton/20260504 - Repte Damm Interhack BCN.docx` — Catalan version.
- `data/raw/Hackaton/INTERHACK Barcelona 2026.pptx` — corporate intro (4 slides).
- `data/raw/Hackaton/Reparto03.07.24.pptx` — DR/DD code system explanation (5 slides) + SAP screenshots.
- `data/raw/Hackaton/Fotos Mollet/20260506 - Presentacio Damm i repte.pptx` — public challenge presentation (16 slides). **The most useful PPTX**: defines what they want and don't want, fleet, retornables flow, evaluation criteria.
- **PDFs from a real day (2026-05-08)**:
  - `Albaran.pdf` — delivery note for client 412 COFFEE & BEER.
  - `Hoja Carga.pdf` — picker's loading list (NºCarga 11764300, 5 pages, 815 cases). Ordered alphabetically by warehouse location.
  - `Hoja Ruta.pdf` — driver's stop list (same NºCarga). Ordered geographically.
- `Hackaton.xlsx`, `ZM040.XLSX`, `Horarios Entrega.XLSX`, `Layout Mollet.xlsx` — original sources of the CSVs.

### Photos

- `data/raw/Hackaton/Fotos Mollet/` — **47 JPEG photos** (15.50.11 sequence: warehouse overview; 20.42–20.43 sequence: trucks loading + warehouse aisles; 15.58.42: pallet detail).

---

## 2. Headline numbers

### Activity volume
- Period covered: **2026-01-30 → 2026-03-31** (~43 working days).
- **20.7 transports per day** on average (range 4–30). Pattern: Friday is the peak (221 transports), Monday is heavy (209), Tue/Wed/Thu lighter (~150 each), Sat/Sun zero.
- **207 deliveries per day** on average (max 303).

### Per transport
- 889 unique transports.
- Median **10 deliveries / transport** (max 32).
- Median **93 albarán lines / transport** (max 285).
- 18 active routes (DR0001, DR0006, DR0010, DR0011, DR0016, DR0017, DR0023, DR0027, DR0031, DR0032, DR0038, DR0040, DR0045, DR0050, DR0051, DR0052, DR0054, DA0216). Six more routes are defined in `ZONAS.csv` but had zero activity in the data: DR0007, DR0046, DR0047, DR0048, DR0053, DR0GEN.
- **Drivers commonly run multiple transports per day**: 70 % do 1, 20 % do 2, the rest do up to 9. So a transport ≠ a day. Routing horizon is per transport.
- Driver↔Route is *almost* 1:1: 17 drivers cover one route each, but **driver 850004 (Fran Romero) covers 3 routes** (DR0001, DR0027, DR0038) over the period — flexible / cover driver.
- **873 / 1.203 clients (73 %) appear on more than one DR route** across the period. Their home zone is fixed but the operative route that picks them up varies day to day.

### Per delivery (client × day)
- Median **9 lines / delivery**, max 74.
- Median **19 unit-of-measure totals / delivery**, max 6.369.

### SKU footprint
- **1.489 distinct SKUs** delivered.
- ZM040 catalogues 7.478 SKUs total; 1.444 of them appear in our deliveries; **45 SKUs in deliveries have no ZM040 entry** — almost all of them retornables (see `06_returnables.md`).
- Top 5 by units delivered:
  1. **CJ13** — empty 1/3 returnable case (46.239) → reverse logistics
  2. **ED13** — Estrella Damm 1/3 RET (31.750)
  3. **UE975** — paper cup 33 cl (31.252)
  4. **CJ15** — empty 1/5 returnable case (8.908) → reverse logistics
  5. **ED15LN** — Estrella Damm 1/5 LN (8.280)

### Clients and geography
- **1.203 unique clients** in deliveries: 1.180 with 10-digit codes (`91xxxxxxxx`) + 23 with 6-digit codes (chains: BK, Taco Bell, UDON, Frankfurt, CIRSA, INDOORWALL VIC, EUREST, DISTRIDAM…).
- Master `Direcciones.csv` has 1.368 rows but only 1.203 unique clients (165 exact-duplicate rows). 165 dormant clients in master never appear in deliveries.
- 111 distinct municipalities (with accent variants → really ~95-100 unique towns once normalised).
- Top: Granollers (241 clients), Vic (211), Mollet del Vallès (183 + 46 with accent variant = 229), Manlleu (60), Sant Boi (55).
- **99 % of clients are in Barcelona province** (CP 08…). 15 in Girona (17…), 1 in Lleida (25…). Effectively a single-province operation.

### Time windows
- The horarios file lists 240 deudores across 1.015 rows, **but only 120 of them are active customers in our deliveries** → real coverage is 120 / 1.203 ≈ **10 %** of active clients.
- Days present: 1–5 + 7 (Mon-Fri + Sun). Saturday implicit closed.
- Two shifts (`Turno`): 1 = morning, 2 = afternoon. Up to 10 windows per client.
- 82 windows flagged `Cierre Si/No = X` (closed). 80 with `00:00–00:00`. 87 windows are < 30 min (very tight). 5 windows for `JUMPING SEA` use the Excel artefact `1 day, 0:00:00`.

### Retornables
- **31 % of all albarán lines** are retornable items (CJ*, 3ENV*, BRL*V, *V).
- **78.8 % of deliveries** carry at least one retornable line.
- **Pattern is 1:1**: every full case (`ED13`) on the albarán has a corresponding empty case (`CJ13`) on the same albarán. The customer "pays" for the full and "credits back" the empty. Physically, the swap happens at the door.

### Units of measure (`Un.medida venta`)
| UMV | Lines | What it is |
|---|---:|---|
| CAJ | 63.610 | Case (24 bottles, 12 Veri cases…) |
| UN | 8.420 | Single unit (barrica, garrafa, cup, brick…) |
| BRL | 6.553 | Barrel (20 L / 30 L / siphons) |
| BOT | 3.013 | Bottle |
| TB | 488 | Tube (CO₂, gas) |
| PAK | 373 | Multi-pack |
| ZPR | 257 | Promo unit |
| EST | 120 | Box / case (estuche) |
| PQ, TIR, BID | < 20 | Pack, strip, jerrycan |

---

## 3. Open questions about the data

(See `QUESTIONS.md` for all of them.)

- **Is the CSV row order the actual delivery order?** Strong hypothesis yes (zones progress monotonically in tested transports), but unconfirmed.
- **What's the truck assigned to each transport?** No `Vehículo` column in the CSVs.
- **Real picking and unloading times.** Not in the data.
- **Trip Priority Number per (client, transport)** — present in SAP, not in the CSVs.
