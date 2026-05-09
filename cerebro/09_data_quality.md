# 09 — Data Quality Report

What we found when we audited every CSV column-by-column. Read this before writing any ETL code, or you'll trip on the same mines we did.

---

## TL;DR

The data is mostly usable but has **structural quirks** in three of the seven CSVs (`ZONAS`, `Cabecera_Transporte`, `Detalle_entrega`) and **dimensional gaps** in `ZM040` for ~65 % of the (material, UMA) pairs we actually use. Every section below names the trap and the workaround.

---

## Trap 1 — Two `Destinatario mcía.` columns, opposite meanings across tables

In `Detalle_entrega.csv`:
- `Destinatario mcía.` (col 5) = **driver name** (e.g. `JACINT MAS CORNET`).
- `Destinatario mcía..1` (col 11) = **client code** (e.g. `9100696143`).

In `Cabecera_Transporte.csv`:
- `Destinatario mcía.` (col 7) = **client code** (e.g. `9100696143`).
- `Destinatario mcía..1` (col 8) = **client name** (e.g. `LOS TERESITOS`).

The header is reused with **inverted semantics**. Always check column position + sample values before joining.

---

## Trap 2 — `Cabecera_Transporte.csv` has named-blank columns

The CSV has `Unnamed: 0` (always blank, throwaway) and `Unnamed: 5` which actually contains the **driver's full name**. Treat the column layout as:

```
[blank] | Entrega | Nº Transporte | Creado el | Repartidor (cód) | NombreRepartidor |
ClienteCód | ClienteNombre
```

| Repartidor | Nombre |
|---|---|
| 850000 | REPARTIDOR MOVI (genérico) |
| 850001 | JUAN JAVIER PONCE |
| 850004 | FRAN ROMERO PONCE |
| 850006 | JOSE VELEZ CASTRO |
| 850009 | ADRIA RAMOS ROSICH |
| 850010 | ANTONIO DIAZ AGUILA |
| 850011 | DAVID SEGOVIA ARMERO |
| 850012 | JORDI PUIGDELLIRE GALERA |
| 850013 | JOSE MARIA SORIA JURADO |
| 850014 | LLUIS CORS BOIX |
| 850018 | RUBEN DIAZ |
| 850021 | LUIS HERNANDEZ MESA |
| 850084 | CRISTIAN LORENTE AINAUD |
| 855184 | MANUEL ANDRADES JIMENEZ |
| 855189 | ALEXANDER JOSE DUGARTE NUNEZ |
| 855190 | PEREZ PEREZ NEWMAN GREGORIO |
| 855203 | JACINT MAS CORNET |
| 855205 | JORGE ESCALANTE GUARERAY |

Total: **18 active drivers**.

---

## Trap 3 — `ZONAS.csv` is two tables mashed into one

Looks like 14 columns. Actually it's **two unrelated tables pasted side-by-side** in Excel, then exported flat:

- **Block A (cols 0-5)**: `ZONAS, NOMBRE ZONAS, _, _, cliente zona, ZonaTransp` → maps **client → zone**. 1.203 rows (one per client).
- **Block B (cols 10-13)**: `ZonaTransp.1, Zona Entrega, RutReal, Denominación` → maps **zone → route**. 70 unique rows (one per zone, padded with blanks).
- Cols 2, 3, 6, 7, 8, 9 are 100 % empty — they're just visual spacers in the original Excel.

The two tables are **not row-aligned**: row 50 in Block A doesn't relate to row 50 in Block B. Read each block independently and join via `ZonaTransp == ZonaTransp.1`.

### Zone domains don't fully overlap

- `ZonaTransp` (Block A, assigned to clients): 56 unique values.
- `ZonaTransp.1` (Block B, defined zones): 69 unique values.
- 14 zones are **defined but have no clients assigned**: `DD13100005, DD13100010, DD13100036, DD13100037, DD13100039, DD13100041, DD13100042, DD13100044, DD13100048, DD13100056, DD13100057, DD13100064, DD13100065, DD13100066`.
- 1 zone is **assigned to a client but not defined**: `DD47100029` (only one client, possibly a typo for DD13100029).

---

## Trap 4 — Two client-code formats (10-digit vs 6-digit)

`Cliente` codes come in two lengths:
- **10-digit `91xxxxxxxx`** (1.180 unique in deliveries) — standard SAP "Deudor" individual customer.
- **6-digit `1xxxxx`** (23 unique in deliveries) — **chain customers**: BK MOLLET, BK VIC, BK GRANOLLERS RONDA SUD, TACO BELL VIC, UDON GRANOLLERS, FRANKFURT LEO BOECK, INDOORWALL VIC, PARADOR VIC-SAU, CIRSA salons, EUREST (catering), DISTRIDAM (Damm subsidiary itself, code 100423).

**149 short codes exist in the master**; only 23 of them appear in deliveries — the others are dormant chain accounts.

When joining tables, do **not** assume client codes are uniformly 10 digits. Treat as string, not int.

---

## Trap 5 — `Direcciones.csv` has 165 exact duplicates

1.368 rows but only **1.203 unique clients**. Some clients appear up to 6 times with **identical** values across all columns (e.g. `BK MOLLET 119751` appears 6 times). Definitely dedupe before joining.

```python
direcciones = pd.read_csv(...).drop_duplicates(subset=['Cliente'])
```

---

## Trap 6 — Town names with accent variants (will break grouping)

The same town appears multiple times with different spellings:

| Same town, multiple spellings |
|---|
| `MOLLET DEL VALLES` / `MOLLET DEL VALLÈS` (3 variants) |
| `MONTORNES DEL VALLES` / `MONTORNÈS DEL VALLÈS` (3 variants) |
| `GRANOLLERS` (2 variants — different casings or trailing chars) |
| `LA ROCA DEL VALLES` / `LA ROCA DEL VALLÈS` |
| `LES FRANQUESES DEL VALLES` / `LES FRANQUESES DEL VALLÈS` |
| `LLIÇÀ D'AMUNT` / `LLICA D'AMUNT` |
| `LLIÇÀ DE VALL` / `LLICA DE VALL` |
| `MONTMELÓ` / `MONTMELO` |
| `PARETS DEL VALLES` / `PARETS DEL VALLÈS` |
| `SANTA EULÀLIA DE RONÇANA` / `SANTA EULALIA DE RONCANA` |
| `TAVERNOLES` / `TAVÈRNOLES` |
| `TORELLÓ` / `TORELLO` |
| `VILANOVA DEL VALLÈS` / `VILANOVA DEL VALLES` |

**Always normalise** (NFD + strip accents + uppercase) before grouping by town. Otherwise you'll fragment client clusters.

There's also one Latin-1 → UTF-8 encoding artefact: `CALLE FRANCESC DE MACIÃ€ I LLUSS 44` — should be `MACIÀ`. Affects 1 client (127151).

---

## Trap 7 — ZM040 has dimensional gaps

We use 1.517 distinct (Material, UMA) combos in deliveries. Of those:
- **45 combos have no ZM040 entry at all** — almost all retornables: `CJ13, CJ15, CJ12V, CJ13V, CJ11V, BRL30V, BRL20V, BRL18V, BT12V, BT13, 3ENV0017, 3ENV0021, …, 3ENV1295, 3ENV0576, …`
- **990 combos have an entry but with `Longitud = Ancho = Altura = 0`** — the master has the row but no per-UMA dimensions.
- **Only 437 combos (29 %)** have usable dims directly.

### Workaround for the 990 gaps

For materials with at least one UMA having dims (typically PAL or UN), extrapolate the missing dims using the `Contador` field (units per pallet). Example: ED13 has dims for PAL (60 cases per pallet) and CAJ; if VO13's CAJ has dims=0 but PAL has dims=100×120×169 with Contador=60, then CAJ ≈ PAL_volume / 60.

### Workaround for the 45 returnables

Map to their full counterpart and copy dimensions (see `06_returnables.md`):
- `CJ13` → `ED13` cases
- `BRL30V` → `ED30` barrels
- `3ENV0xxx` → nearest matching full counterpart (heuristic)

---

## Quirk 1 — Drivers do multiple transports per day (we got this wrong before)

Distribution of **(Date, Driver) → number of transports**:

| transports/day | (Date, Driver) pairs |
|---:|---:|
| 1 | 474 (70 %) |
| 2 | 133 (20 %) |
| 3 | 28 |
| 4 | 4 |
| 5 | 2 |
| 7 | 2 |
| 8 | 2 |
| 9 | 1 |

**30 % of (date, driver) pairs run multiple transports per day.** Some drivers do up to 9. This breaks any "one truck = one trip per day" assumption. A driver returning to base, refilling, and leaving again is normal.

Implication: routing horizon is **per transport**, not per day. We optimise individual transports, not driver-day schedules.

---

## Quirk 2 — Driver↔Route is *almost* 1:1, but not quite

- 17 drivers each cover exactly 1 route.
- **Driver 850004 (FRAN ROMERO) covers 3 routes**: DR0027, DR0038, DR0001 (over the period). Likely a flexible / cover driver.
- DR0001 is associated with 2 different drivers across the period (one from 855xxx series, plus 850004 occasionally).

So the model "driver → route → vehicle" has a 1:N exception we should be aware of.

---

## Quirk 3 — Clients move between routes

- 873 of 1.203 clients (73 %) appear in **more than one DR route** during the data period.
- But every client has **exactly one** `ZonaTransp` (their home zone).
- And every zone has **exactly one** RutReal in `ZONAS.csv`.

How can a client end up in multiple routes if its zone is fixed? Two hypotheses:
1. The route `Ruta` field in `Detalle_entrega` is **the route that actually delivered it on that day**, not the route the client is normatively assigned to. So when DR0010 spills volume into DR0011, some DR0010 customers ride on DR0011 that day.
2. Some clients (chain stores, multi-location) span more than one zone in practice.

→ Worth confirming with mentors. Tracked as Q11.

---

## Quirk 4 — Multiple lines for the same (Entrega, Material)

In 9.500 rows, the same (Entrega, Material) appears 2+ times with **different quantities**, sometimes the same UMV. Example for delivery 827937487:

```
CJ13 CAJ 2 ← line 1
CJ13 CAJ 1 ← line 2 (same material, same UMV)
ED13 CAJ 2
ED13 CAJ 1
```

Plausible reasons (any or all):
- Different price tier / promotion lots
- Different SAP sales orders consolidated on one albarán
- Different batches / Lote tracking

For volume planning, **sum the qty across all lines of the same (Entrega, Material, UMV)**. There are also 117 entregas where the same material appears with **different UMV** in the same albarán (e.g. some CAJ + some UN) — keep them separate, they consume different unit volumes.

---

## Quirk 5 — `Horarios_Entrega.csv` reality vs. headline number

The file has **1.015 rows × 240 unique deudores**. Of those 240:
- **120 are clients that actually show up in deliveries** (within our 43-day window).
- 120 are configured but didn't order during the period (dormant accounts).

So **only ~10 % of active customers (120 / 1.203) have explicit time windows** — not the 20 % we previously thought.

Patterns inside Horarios:
- **82 rows have `Cierre Si/No = X`** → that day/shift is closed.
- **80 rows have window 00:00–00:00** (also closed).
- **368 rows start at 00:00:00** (likely "no morning restriction").
- **310 rows end at 18:00:00** (the most common cutoff).
- **5 rows for `JUMPING SEA` (cliente 9100691361)** end at `1 day, 0:00:00` — Excel artefact; means "until midnight next day" → effectively 24 h window.
- **2 rows for genuine 00:00–23:59** (open all day).
- 87 rows have windows shorter than 30 min — these need to be carefully respected.
- Days of week: `1, 2, 3, 4, 5, 7` — Monday to Friday + Sunday. **Saturday (day 6) is implicit "closed everywhere"** for clients in Horarios.
- 2 shifts (`Turno 1, 2`) per day → up to 10 windows per client (Mon-Fri × 2 + Sun × 2).
- The 4 categorical fields (`Organización ventas=235, Canal distribución=1, Sector=8, Descripción=DDI MOLLET, …`) are constant across the file — they're identifiers of the org-channel, not features we need.

---

## Quirk 6 — `Materiales_zubic.csv` has 167 rows with no Almacén / UMB / Fabricante

11 % of the materials master has missing Alm. / UMB / Fabricante / Número de un fabricante. They still have `Material`, `Denominación` (`Número de material`) and `Ubic.`, so they're not completely useless — but expect joins to lose them.

---

## Quirk 7 — Refrigerated SKUs **do** exist (we previously assumed not)

A handful of materials have `Ubic. = CAMARA` in `Materiales_zubic.csv`, e.g. **0LT0021 — CACAOLAT MINIBRIK SLIM 20CL P6 24U**. Those are refrigerated.

Implication: we cannot blanket-state "no cold chain". The **assumption A10 in `ASSUMPTIONS.md` is partly wrong** and should be qualified to "the vast majority is ambient, but there's a small refrigerated subset".

---

## Quirk 8 — Non-geometric warehouse locations are bigger than we thought

Of 1.489 SKUs in the warehouse:
- Only **213 sit in a "real" rack position** (`AA01A2`-style code).
- **1.131 sit in `ZCG`** (Comergrup zone) — no precise rack, just "go to the Comergrup area and pick".
- 49 in `PLV`, 44 in `A0DISTRIDA`, 42 in `ENVASE`, plus a handful in special / oddly-formatted locations (`CAMARA`, `AAAAAA`, `BA001A2` typo, etc.).

So **76 % of the catalogue lives in zone-coded "areas" rather than precise positions**. The picker walks to the area and finds the SKU there. This dramatically simplifies the warehouse model — most SKUs are looked up by zone, not by `Pasillo×Posición×Nivel`.

### Top fabricantes (manufacturer / origin)

| Manufacturer | SKUs in Mollet |
|---|---:|
| COMERGRUP, S.L. | 171 |
| (blank) | 168 |
| S.A. DAMM | 91 |
| DDI PROVEA S.L (CENTRAL) | 78 |
| ECKES GRANINI IBERICA | 47 |
| PREMIUM MIX GROUP | 46 |
| CHOVI | 45 |
| GOMA CAMPS | 41 |
| COMERCIAL GALLO | 30 |
| ESPINALER 1896 | 26 |

DDI distributes a much wider portfolio than just Damm beverages. **Damm-branded products are only 91 of 1.489 SKUs (6 %)**.

---

## Quirk 9 — ZM040 hierarchy field encodes family + packaging

The field `Jquía.productos` (e.g. `00CF30ZZPCA1E4`) is a structured code with 855 unique values. It can be parsed:

- **Chars 0-3**: family (`00AM` = alimentación, `00LM` = limpieza, `00LI` = licor, `00VE` = vino, `00RF` = refresco, `00ZU` = zumo, `00CF` = café, `00AG` = agua, `00LT` = lácteos, `00CZ` = cerveza, `00NV` = no-Damm beverages, `00RA` = ratafia, `01CZ` / `01CF` / `01LI` = parallel categories).
- **Chars 4-5**: subfamily (e.g. `81`, `74`, `82`, `91`, `87`, …).
- **Chars 6-9**: brand / sub-brand code.
- **Chars 10-13**: packaging type (`DIE4`, `DIE3`, `RPE4`, `12E4`, `13E4`, `02E4`, `A1E4`, …). Likely encodes capacity + format + retornable flag.

We can use this to **cluster SKUs into operational families** for warehouse picking and packaging assumptions. Worth a Q-mark to confirm the exact decoding with mentors.

---

## Quirk 10 — `_uma` codes that aren't operational packaging

`ZM040.UMA` includes 50+ codes; many are SAP-internal ratios, not physical units:

| Operational (use these for volume) | SAP-internal (ignore for packing) |
|---|---|
| **PAL** = pallet | ZPR = ratio promo |
| **CAJ** = case | ZCE = ratio centena |
| **UN** = single unit | ZPE / ZOP / ZPM / ZPA = ratios pedido / oferta / margen / capacidad |
| **BOT** = bottle | CAM = container |
| **BRL** = barrel | MNT = montaje? |
| **PAK** = pack | GRP = grupo |
| **EST** = estuche | KGL = kilo-litro |
| **LAT** = lata | V%, G/L = density / volumetric |
| | Y04, Y05, Y17, Y28, Y34, Y35, Y53, K, KIT, JG, BOL, BIB, JAU, BOX, ADR, SDF = SAP misc |

Use the operational set for our volume model.

---

## Quirk 11 — Cantidad entrega max value (6.000 vasos)

The largest line in our data is **6.000 vasos de papel** (UE975, paper cups) on a single albarán. This is real (paper cups are bought in big batches by busy bars) but it's outsized. The next biggest is 3.000. Make sure your models don't choke on these outliers — they aren't errors.

There are no negative quantities, no zeros, no decimals.

---

## Things that turned out to be CLEAN

To avoid premature paranoia:
- Every `Entrega` in `Cabecera_Transporte` exists in `Detalle_entrega` (no orphan deliveries either way).
- Every `Cliente` in deliveries has an entry in `Direcciones`.
- Every `Cliente` in deliveries has an entry in `ZONAS` (block A).
- Every `Transporte` has exactly one driver and one date.
- Every `Entrega` belongs to exactly one transport.
- No empty/null in critical fields (FECHA, Material, Cantidad, etc.) of `Detalle_entrega`.
- Every CP is exactly 5 digits.
- Every quantity is positive.
- 99 % of clients are in Barcelona province (CP `08…`); 15 in Girona (`17…`), 1 in Lleida (`25…`).

---

## Suggested ETL hygiene checklist

```python
# 1) Dedupe
direcciones = direcciones.drop_duplicates('Cliente')

# 2) Strip column names
df.columns = [c.strip() for c in df.columns]

# 3) Normalise text fields
import unicodedata
def norm(s):
 return ''.join(c for c in unicodedata.normalize('NFD', s.strip())
 if unicodedata.category(c) != 'Mn').upper()

# 4) ZONAS: split into two tables BEFORE joining
zonas_block_a = zonas[['cliente zona', 'ZonaTransp']].rename(
 columns={'cliente zona': 'cliente'}).dropna()
zonas_block_b = zonas[['ZonaTransp.1', 'Zona Entrega', 'RutReal', 'Denominación']
 ].drop_duplicates().dropna()

# 5) Cabecera: rename Unnamed columns
cabecera = cabecera.rename(columns={
 'Unnamed: 0': 'placeholder',
 'Unnamed: 5': 'NombreRepartidor',
 'Destinatario mcía.': 'ClienteCod',
 'Destinatario mcía..1': 'ClienteNombre',
})

# 6) Detalle: rename for clarity
detalle = detalle.rename(columns={
 'Destinatario mcía.': 'NombreRepartidor',
 'Destinatario mcía..1': 'ClienteCod',
 'ZonaTransp': 'ZonaTranspCod',
 'ZonaTransp.1': 'ZonaTranspNombre',
})
detalle = detalle.drop(columns=['Unnamed: 18']) # 100 % empty

# 7) Cliente as string (not int) — to preserve 6-digit codes too
df['Cliente'] = df['Cliente'].astype(str).str.strip()
```
