from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "csv"
OUT = ROOT / "outputs"

HACKATON = DATA / "Hackaton"
ZM040 = DATA / "ZM040"

DEMO_DATE = "2026-02-27"
DDI_MOLLET = {"lat": 41.5417, "lon": 2.2126, "name": "DDI Mollet"}
TRUCK_SIZES = (3, 6, 8)
