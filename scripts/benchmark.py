"""Benchmark Star-cubing against a simple BUC-style baseline.

The script uses the processed SASHTS dataset, expands it by sampling with
replacement when a target benchmark size is larger than the source data, and
writes CSV/chart outputs for Task 15.

Run from the repository root:

    python scripts/benchmark.py
"""

from __future__ import annotations

import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.algorithm.starcubing import starcubing  # noqa: E402
from src.star_tree import StarTree  # noqa: E402


DATA_PATH = PROJECT_ROOT / "data" / "processed" / "sashts_final_dataset.csv"
RESULTS_PATH = PROJECT_ROOT / "reports" / "benchmark_results.csv"
CHART_DIR = PROJECT_ROOT / "docs" / "charts"

DATASET_SIZES = [10_000, 50_000, 100_000, 500_000, 1_000_000]
BUC_TIMEOUT_SECONDS = 120.0
MAX_BENCHMARK_DIMENSIONS = 6
RANDOM_STATE = 42

PREFERRED_DIMENSIONS = [
    "month_id",
    "ind1_site",
    "ind2_site",
    "pair_sars",
    "contacts",
    "hcir",
    "hh_ar",
    "ind1_agegrp9",
    "ind2_agegrp9",
]


class BenchmarkTimeout(RuntimeError):
    """Raised when a benchmark implementation exceeds its time budget."""


def load_dataset(data_path: Path = DATA_PATH) -> pd.DataFrame:
    """Load the processed dataset used as benchmark source data."""

    if not data_path.exists():
        raise FileNotFoundError(f"Processed dataset not found: {data_path}")
    return pd.read_csv(data_path, encoding="utf-8-sig")


def expand_dataset(df: pd.DataFrame, target_size: int) -> pd.DataFrame:
    """Return exactly ``target_size`` rows, sampling with replacement if needed."""

    if target_size <= len(df):
        return df.head(target_size).copy()
    return df.sample(n=target_size, replace=True, random_state=RANDOM_STATE).reset_index(drop=True)


def dynamic_min_sup(dataset_size: int) -> int:
    """Scale support threshold with benchmark size to make pruning meaningful."""

    return max(50, int(0.005 * dataset_size))


def select_benchmark_dimensions(df: pd.DataFrame, max_dimensions: int = MAX_BENCHMARK_DIMENSIONS) -> list[str]:
    """Select low-cardinality dimensions suitable for cubing benchmarks."""

    selected: list[str] = []
    for column in PREFERRED_DIMENSIONS:
        if column in df.columns and 1 < df[column].nunique(dropna=False) <= 50:
            selected.append(column)
        if len(selected) >= max_dimensions:
            return selected

    for column in df.columns:
        if column in selected:
            continue
        if 1 < df[column].nunique(dropna=False) <= 25:
            selected.append(column)
        if len(selected) >= max_dimensions:
            return selected

    if len(selected) < 2:
        raise ValueError("Could not detect enough low-cardinality columns for benchmarking.")
    return selected


def _prepare_transactions(df: pd.DataFrame, dimensions: list[str]) -> list[tuple[str, ...]]:
    return [tuple(row) for row in df[dimensions].astype(str).itertuples(index=False, name=None)]


def measure_performance(func: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Measure runtime and peak Python memory allocated by a benchmark function."""

    tracemalloc.start()
    start_time = time.perf_counter()
    try:
        payload = func(*args, **kwargs)
        status = payload.get("status", "ok")
    except BenchmarkTimeout:
        payload = {"num_cuboids": None}
        status = "timeout"
    except Exception as exc:  # Keep the benchmark report complete.
        payload = {"num_cuboids": None, "error": str(exc)}
        status = "error"
    runtime_seconds = time.perf_counter() - start_time
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "runtime_seconds": round(runtime_seconds, 6),
        "peak_memory_mb": round(peak_bytes / (1024 * 1024), 6),
        "num_cuboids": payload.get("num_cuboids"),
        "status": status,
        "error": payload.get("error"),
    }


def run_star_cubing_benchmark(
    transactions: list[tuple[str, ...]],
    dimensions: list[str],
    min_sup: int,
) -> dict[str, Any]:
    """Run the existing StarTree + Star-cubing implementation."""

    tree = StarTree(dimensions, min_support=min_sup)
    tree.build_from_transactions(transactions)
    cuboids = starcubing(tree, min_sup=min_sup)
    return {"num_cuboids": len(cuboids), "status": "ok"}


def run_buc_benchmark(
    transactions: list[tuple[str, ...]],
    dimensions: list[str],
    min_sup: int,
    timeout_seconds: float = BUC_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run a pure-Python recursive BUC-style baseline.

    Pandas is deliberately not used here. Both Star-Cubing and BUC receive the
    same transaction tuples. The baseline recursively partitions records by
    each dimension, emits supported cuboids, and explores deeper dimensions only
    for groups that meet ``min_sup``.
    """

    start_time = time.perf_counter()
    cuboids: set[tuple[str, ...]] = set()
    dimension_count = len(dimensions)

    def check_timeout() -> None:
        if time.perf_counter() - start_time > timeout_seconds:
            raise BenchmarkTimeout()

    def recurse(rows: list[tuple[str, ...]], start_dimension: int, prefix: dict[int, str]) -> None:
        check_timeout()
        for dimension_index in range(start_dimension, dimension_count):
            groups: dict[str, list[tuple[str, ...]]] = defaultdict(list)
            for row in rows:
                groups[row[dimension_index]].append(row)

            for value, group_rows in groups.items():
                support = len(group_rows)
                if support < min_sup:
                    continue
                cuboid = ["*"] * dimension_count
                for prefix_dimension, prefix_value in prefix.items():
                    cuboid[prefix_dimension] = prefix_value
                cuboid[dimension_index] = value
                cuboids.add(tuple(cuboid))
                recurse(group_rows, dimension_index + 1, {**prefix, dimension_index: value})

    # Materialize exact full-dimensional supports first, then recursively
    # explore lower-dimensional BUC partitions with support pruning.
    for values, support in Counter(transactions).items():
        check_timeout()
        if support >= min_sup:
            cuboids.add(values)

    try:
        recurse(transactions, 0, {})
    except RecursionError as exc:
        raise BenchmarkTimeout() from exc

    return {"num_cuboids": len(cuboids), "status": "ok"}


def save_results(results: list[dict[str, Any]], results_path: Path = RESULTS_PATH) -> None:
    results_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(results_path, index=False)
    print(f"Saved benchmark results to {results_path}")


def _plot_metric(results_df: pd.DataFrame, metric: str, ylabel: str, output_path: Path) -> None:
    plt.figure(figsize=(9, 5))
    for algorithm, group in results_df.groupby("algorithm"):
        ok_group = group[group["status"] == "ok"].sort_values("dataset_size")
        if ok_group.empty:
            continue
        plt.plot(ok_group["dataset_size"], ok_group[metric], marker="o", linewidth=2, label=algorithm)
    plt.title(ylabel)
    plt.xlabel("Dataset size")
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def plot_results(results: list[dict[str, Any]], chart_dir: Path = CHART_DIR) -> None:
    chart_dir.mkdir(parents=True, exist_ok=True)
    results_df = pd.DataFrame(results)
    _plot_metric(results_df, "runtime_seconds", "Runtime seconds", chart_dir / "benchmark_time.png")
    _plot_metric(results_df, "peak_memory_mb", "Peak memory MB", chart_dir / "benchmark_memory.png")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for algorithm, group in results_df.groupby("algorithm"):
        ok_group = group[group["status"] == "ok"].sort_values("dataset_size")
        if ok_group.empty:
            continue
        axes[0].plot(ok_group["dataset_size"], ok_group["runtime_seconds"], marker="o", label=algorithm)
        axes[1].plot(ok_group["dataset_size"], ok_group["peak_memory_mb"], marker="o", label=algorithm)
    axes[0].set_title("Runtime seconds")
    axes[1].set_title("Peak memory MB")
    for axis in axes:
        axis.set_xlabel("Dataset size")
        axis.grid(True, alpha=0.3)
        axis.legend()
    axes[0].set_ylabel("Seconds")
    axes[1].set_ylabel("MB")
    fig.tight_layout()
    fig.savefig(chart_dir / "benchmark_time_memory_summary.png", dpi=160)
    plt.close(fig)
    print(f"Saved benchmark charts to {chart_dir}")


def run_benchmarks() -> list[dict[str, Any]]:
    source_df = load_dataset()
    dimensions = select_benchmark_dimensions(source_df)
    print(f"Benchmark dimensions: {', '.join(dimensions)}")
    print(f"Dynamic min_sup=max(50, int(0.005 * dataset_size)), BUC timeout={BUC_TIMEOUT_SECONDS}s")

    results: list[dict[str, Any]] = []
    for dataset_size in DATASET_SIZES:
        print(f"Benchmarking size: {dataset_size}")
        min_sup = dynamic_min_sup(dataset_size)
        print(f"min_sup: {min_sup}")
        benchmark_df = expand_dataset(source_df, dataset_size)
        transactions = _prepare_transactions(benchmark_df, dimensions)

        star_result = measure_performance(run_star_cubing_benchmark, transactions, dimensions, min_sup)
        print(
            "Star-cubing time: "
            f"{star_result['runtime_seconds']}s, memory: {star_result['peak_memory_mb']}MB, status: {star_result['status']}"
        )
        results.append({"dataset_size": dataset_size, "min_sup": min_sup, "algorithm": "Star-cubing", **star_result})

        buc_result = measure_performance(run_buc_benchmark, transactions, dimensions, min_sup, BUC_TIMEOUT_SECONDS)
        print(
            "BUC time: "
            f"{buc_result['runtime_seconds']}s, memory: {buc_result['peak_memory_mb']}MB, status: {buc_result['status']}"
        )
        results.append({"dataset_size": dataset_size, "min_sup": min_sup, "algorithm": "BUC baseline", **buc_result})

    return results


def main() -> None:
    results = run_benchmarks()
    save_results(results)
    plot_results(results)


if __name__ == "__main__":
    main()
