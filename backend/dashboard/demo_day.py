import pandas as pd

from paths import DEMO_DATE, OUT


def build_demo_dataset(date=DEMO_DATE):
    deliveries = pd.read_parquet(OUT / "deliveries.parquet")
    geo = pd.read_parquet(OUT / "geocoded.parquet")
    deliveries["fecha"] = pd.to_datetime(deliveries["fecha"])
    day = deliveries[deliveries["fecha"] == pd.Timestamp(date)].copy()
    day = day.merge(geo[["cliente", "lat", "lon"]], on="cliente", how="left")
    day = day[day["lat"].notna()].copy()
    day.to_parquet(OUT / "demo_day.parquet", index=False)
    print(
        f"Day {date}: {day['transporte'].nunique()} transports, "
        f"{day['cliente'].nunique()} clients, {day['entrega'].nunique()} deliveries, "
        f"{day['palets_total'].sum():.1f} pallets"
    )
    return day


if __name__ == "__main__":
    build_demo_dataset()
