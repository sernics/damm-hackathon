import pandas as pd

from paths import OUT

CO2_KG_PER_KM = 0.9
URBAN_KMH = 30


def compare(optimized_file="optimized_summary.parquet", output_file="metrics.parquet"):
    baseline = pd.read_parquet(OUT / "baseline_summary.parquet")
    optimized = pd.read_parquet(OUT / optimized_file)
    baseline_km = float(baseline["distance_km"].sum())
    optimized_km = float(optimized["distance_km"].sum())
    km_saved = baseline_km - optimized_km
    metrics = {
        "baseline_km": baseline_km,
        "optimized_km": optimized_km,
        "km_saved": km_saved,
        "km_saved_pct": km_saved / baseline_km * 100 if baseline_km else 0.0,
        "baseline_avg_occupation_pct": float(baseline["occupation_pct"].mean()),
        "optimized_avg_occupation_pct": float(optimized["occupation_pct"].mean()),
        "co2_saved_kg": km_saved * CO2_KG_PER_KM,
        "time_saved_min": km_saved / URBAN_KMH * 60,
        "baseline_trucks": int(len(baseline)),
        "optimized_trucks": int(len(optimized)),
    }
    out = pd.DataFrame([metrics])
    out.to_parquet(OUT / output_file, index=False)
    print(
        f"Metrics: {metrics['km_saved']:.1f} km saved "
        f"({metrics['km_saved_pct']:.1f}%), {metrics['co2_saved_kg']:.1f} kg CO2"
    )
    return metrics


if __name__ == "__main__":
    compare()
