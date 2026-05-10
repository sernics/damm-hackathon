from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLUSTER_ROOT = REPO_ROOT / "data/custom/clustering"


@dataclass(frozen=True)
class ClusterPaths:
    source: str
    directory: Path
    clusters_csv: Path
    client_cluster_lookup_csv: Path


def get_cluster_paths(
    cluster_source: str,
    cluster_root: Path | None = None,
) -> ClusterPaths:
    source = cluster_source.strip()
    if not source:
        raise ValueError("cluster_source cannot be empty.")
    if "/" in source or "\\" in source or source in {".", ".."}:
        raise ValueError(f"Invalid cluster_source: {cluster_source!r}")

    root = cluster_root or DEFAULT_CLUSTER_ROOT
    directory = root / source
    return ClusterPaths(
        source=source,
        directory=directory,
        clusters_csv=directory / "clusters.csv",
        client_cluster_lookup_csv=directory / "client_cluster_lookup.csv",
    )


def load_clusters_df(
    cluster_source: str,
    cluster_root: Path | None = None,
) -> pd.DataFrame:
    paths = get_cluster_paths(cluster_source, cluster_root=cluster_root)
    if not paths.clusters_csv.exists():
        raise FileNotFoundError(f"Missing clusters file: {paths.clusters_csv}")

    clusters_df = pd.read_csv(paths.clusters_csv)
    required_columns = {"cluster_id", "cluster_size", "members_json"}
    missing_columns = required_columns - set(clusters_df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing columns in {paths.clusters_csv}: {sorted(missing_columns)}"
        )

    clusters_df = clusters_df.copy()
    clusters_df["members"] = clusters_df["members_json"].map(json.loads)
    clusters_df["cluster_source"] = paths.source
    return clusters_df


def load_cluster_lookup(
    cluster_source: str,
    cluster_root: Path | None = None,
) -> pd.DataFrame:
    paths = get_cluster_paths(cluster_source, cluster_root=cluster_root)
    if not paths.client_cluster_lookup_csv.exists():
        raise FileNotFoundError(
            f"Missing cluster lookup file: {paths.client_cluster_lookup_csv}"
        )

    lookup_df = pd.read_csv(paths.client_cluster_lookup_csv)
    required_columns = {"client_name", "cluster_id", "cluster_size"}
    missing_columns = required_columns - set(lookup_df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing columns in {paths.client_cluster_lookup_csv}: "
            f"{sorted(missing_columns)}"
        )

    lookup_df = lookup_df.copy()
    lookup_df["client_name"] = lookup_df["client_name"].astype(str).str.strip()
    lookup_df = lookup_df[lookup_df["client_name"] != ""].copy()

    if "cluster_source" not in lookup_df.columns:
        lookup_df["cluster_source"] = paths.source

    return lookup_df.drop_duplicates(subset=["client_name"], keep="first")

