import re
import unicodedata

import pandas as pd

from paths import HACKATON, OUT, ZM040


def strip_accents(value):
    if pd.isna(value):
        return value
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", str(value))
        if not unicodedata.combining(char)
    )


def normalize_poblacion(value):
    if pd.isna(value):
        return None
    value = strip_accents(value).upper().strip()
    return re.sub(r"\s+", " ", value)


def load_catalog():
    catalog = pd.read_csv(ZM040 / "Sheet1.csv")
    pallets = (
        catalog[catalog["UMA"] == "PAL"]
        [["Material", "Contador", "Volumen", "Peso bruto"]]
        .rename(
            columns={
                "Contador": "unid_por_palet",
                "Volumen": "volumen_palet_l",
                "Peso bruto": "peso_palet_kg",
            }
        )
        .drop_duplicates(subset="Material")
    )
    hierarchy = catalog[["Material", "Jquía.productos", "Denom."]].drop_duplicates(
        subset="Material"
    )
    hierarchy["familia"] = hierarchy["Jquía.productos"].astype(str).str[:5]
    return pallets.merge(hierarchy[["Material", "familia"]], on="Material", how="left")


def load_addresses():
    addresses = pd.read_csv(HACKATON / "Direcciones.csv")
    addresses = addresses.rename(
        columns={
            "Cliente": "cliente",
            "Nombre 1": "nombre",
            "Calle": "calle",
            "CP": "cp",
            "Población": "poblacion_raw",
        }
    )
    addresses["poblacion"] = addresses["poblacion_raw"].apply(normalize_poblacion)
    addresses["cp"] = addresses["cp"].astype("Int64").astype(str).str.zfill(5)
    addresses["address_full"] = (
        addresses["calle"].fillna("").str.strip()
        + ", "
        + addresses["cp"]
        + " "
        + addresses["poblacion"].fillna("")
        + ", Spain"
    )
    addresses = addresses.drop_duplicates(subset="cliente", keep="first")
    return addresses[["cliente", "nombre", "calle", "cp", "poblacion", "address_full"]]


def load_zones():
    detail = pd.read_csv(HACKATON / "Detalle_entrega.csv", usecols=["Destinatario mcía..1", "Ruta"])
    detail["cliente"] = pd.to_numeric(detail["Destinatario mcía..1"], errors="coerce").astype("Int64")
    detail = detail.dropna(subset=["cliente", "Ruta"])
    counts = detail.groupby(["cliente", "Ruta"]).size().reset_index(name="n")
    principal = (
        counts.sort_values(["cliente", "n"], ascending=[True, False])
        .drop_duplicates(subset="cliente", keep="first")
        .rename(columns={"Ruta": "ruta_principal"})
    )
    return principal[["cliente", "ruta_principal"]]


def load_deliveries(catalog):
    deliveries = pd.read_csv(HACKATON / "Detalle_entrega.csv")
    deliveries = deliveries.rename(
        columns={
            "FECHA": "fecha",
            "Transporte": "transporte",
            "Ruta": "ruta",
            "Repartidor": "repartidor_id",
            "Destinatario mcía.": "repartidor_nombre",
            "Entrega": "entrega",
            "Material": "material",
            "Denominación": "producto",
            "Cantidad entrega": "cantidad",
            "Un.medida venta": "uma",
            "Destinatario mcía..1": "cliente",
        }
    )
    deliveries["cliente"] = pd.to_numeric(deliveries["cliente"], errors="coerce").astype("Int64")
    deliveries["fecha"] = pd.to_datetime(deliveries["fecha"], format="%d/%m/%Y", errors="coerce")
    deliveries = deliveries.merge(
        catalog[["Material", "unid_por_palet", "familia"]].rename(columns={"Material": "material"}),
        on="material",
        how="left",
    )
    median_units = catalog["unid_por_palet"].median()
    deliveries["unid_por_palet"] = deliveries["unid_por_palet"].fillna(median_units)
    deliveries["palets_ocupados"] = deliveries["cantidad"] / deliveries["unid_por_palet"]
    deliveries["retornable"] = deliveries["uma"] == "BRL"
    return deliveries[
        [
            "fecha",
            "transporte",
            "ruta",
            "repartidor_id",
            "repartidor_nombre",
            "entrega",
            "cliente",
            "material",
            "producto",
            "familia",
            "cantidad",
            "uma",
            "unid_por_palet",
            "palets_ocupados",
            "retornable",
        ]
    ]


def build_master_table():
    catalog = load_catalog()
    addresses = load_addresses()
    zones = load_zones()
    deliveries = load_deliveries(catalog)
    master = deliveries.merge(addresses, on="cliente", how="left").merge(zones, on="cliente", how="left")
    return master, addresses


def aggregate_by_delivery(master):
    return (
        master.groupby(
            [
                "fecha",
                "transporte",
                "ruta",
                "entrega",
                "cliente",
                "nombre",
                "calle",
                "cp",
                "poblacion",
                "address_full",
                "ruta_principal",
            ],
            dropna=False,
        )
        .agg(
            palets_total=("palets_ocupados", "sum"),
            num_lineas=("material", "count"),
            cajas_retornables=("retornable", "sum"),
            cantidad_total=("cantidad", "sum"),
        )
        .reset_index()
    )


def aggregate_by_transport(deliveries_agg):
    return (
        deliveries_agg.groupby(["fecha", "transporte", "ruta"])
        .agg(
            palets_total=("palets_total", "sum"),
            num_clientes=("cliente", "nunique"),
            num_lineas=("num_lineas", "sum"),
            cajas_retornables=("cajas_retornables", "sum"),
        )
        .reset_index()
    )


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    master_table, address_table = build_master_table()
    delivery_table = aggregate_by_delivery(master_table)
    transport_table = aggregate_by_transport(delivery_table)
    master_table.to_parquet(OUT / "master.parquet", index=False)
    address_table.to_parquet(OUT / "addresses.parquet", index=False)
    delivery_table.to_parquet(OUT / "deliveries.parquet", index=False)
    transport_table.to_parquet(OUT / "transports.parquet", index=False)
    print(
        f"Built {len(master_table):,} lines, {len(delivery_table):,} stops, "
        f"{len(transport_table):,} transports"
    )
