import matplotlib.pyplot as plt
import pandas as pd

from paths import DDI_MOLLET, OUT


def plot_demo_day():
    day = pd.read_parquet(OUT / "demo_day.parquet")
    transports = sorted(day["transporte"].unique())
    cmap = plt.colormaps["tab20"]
    color_for = {transport: cmap(index % 20) for index, transport in enumerate(transports)}
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    ax.scatter([DDI_MOLLET["lon"]], [DDI_MOLLET["lat"]], c="black", s=300, marker="*", zorder=10, label="DDI Mollet")
    for transport in transports:
        subset = day[day["transporte"] == transport]
        sizes = (subset["palets_total"].clip(lower=0.1) * 60).clip(20, 400)
        ax.scatter(
            subset["lon"],
            subset["lat"],
            c=[color_for[transport]],
            s=sizes,
            alpha=0.7,
            edgecolors="white",
            linewidth=0.5,
        )
    ax.set_title(
        f"Day 2026-02-27: {len(transports)} transports, "
        f"{day['cliente'].nunique()} clients, {day['palets_total'].sum():.1f} pallets"
    )
    ax.grid(True, alpha=0.3)
    ax.set_aspect(1.32)
    plt.tight_layout()
    plt.savefig(OUT / "demo_day_map.png", dpi=120, bbox_inches="tight")
    plt.close()


if __name__ == "__main__":
    plot_demo_day()
