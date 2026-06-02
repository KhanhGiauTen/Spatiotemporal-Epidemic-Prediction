"""Task 14 real-time style alert system.

This module simulates streaming checks by reading batches from the existing
processed SASHTS dataset. When StarTree and Star-Cubing APIs are importable, it
compresses each batch and evaluates cuboid support. If those APIs or suitable
columns are unavailable, it falls back to grouped spatiotemporal contact
patterns from the processed data.

The implementation is intentionally lightweight for a local academic project:
no OS cron, no database, and no model retraining. Run once with:

    python src/alert_system.py

Use ``--loop`` for repeated scheduled checks.
"""

from __future__ import annotations

import argparse
import csv
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

try:
    from .algorithm.starcubing import starcubing
    from .star_tree import StarTree
except ImportError:  # pragma: no cover - supports direct script execution
    from algorithm.starcubing import starcubing
    from star_tree import StarTree


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STREAM_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "sashts_final_dataset.csv"
ALERT_LOG_PATH = PROJECT_ROOT / "alerts.log"

MIN_SUP = 30
CHECK_INTERVAL_SECONDS = 10
STREAM_BATCH_SIZE = 250

PATTERN_COLUMNS = ["month_id", "ind1_site", "ind2_site", "pair_sars"]
RISK_COLUMNS = ["contacts", "contacts_infected", "hcir", "hh_ar"]
MAX_ALERTS_PER_CHECK = 25


@dataclass(frozen=True)
class Alert:
    """A single alert emitted by the simulated stream checker."""

    message: str
    support: int
    min_sup: int
    source: str
    timestamp: str

    def format(self) -> str:
        return f"{self.timestamp} [ALERT] {self.message} support={self.support}, min_sup={self.min_sup}, source={self.source}"


def _clean_row(row: dict[str, str]) -> dict[str, str]:
    return {key.lstrip("\ufeff").strip(): value for key, value in row.items()}


def _to_float(value: str | int | float | None, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_stream_batch(
    data_path: Path = STREAM_DATA_PATH,
    batch_size: int = STREAM_BATCH_SIZE,
    offset: int | None = None,
) -> list[dict[str, str]]:
    """Load or simulate a stream batch from existing processed data.

    If ``offset`` is omitted, the latest ``batch_size`` records are returned.
    If source data is missing, an empty list is returned with a helpful message.
    """

    if not data_path.exists():
        print(f"[alert_system] Missing stream data file: {data_path}")
        return []

    with data_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = [_clean_row(row) for row in csv.DictReader(csv_file)]

    if batch_size < 1:
        return []
    if offset is None:
        return rows[-batch_size:]
    return rows[offset : offset + batch_size]


def _available_columns(records: Sequence[dict[str, str]], columns: Sequence[str]) -> list[str]:
    if not records:
        return []
    return [column for column in columns if column in records[0]]


def _make_alert(message: str, support: int, min_sup: int, source: str) -> Alert:
    return Alert(
        message=message,
        support=support,
        min_sup=min_sup,
        source=source,
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )


def _evaluate_with_star_tree(records: Sequence[dict[str, str]], min_sup: int) -> list[Alert]:
    """Evaluate batch support with StarTree and Star-Cubing when possible."""

    dimensions = _available_columns(records, PATTERN_COLUMNS)
    if len(dimensions) < 2:
        return []

    transactions = [[str(record.get(column, "")) for column in dimensions] for record in records]
    tree = StarTree(dimensions, min_support=max(1, min_sup))
    tree.build_from_transactions(transactions)

    alerts: list[Alert] = []
    for cuboid, support in starcubing(tree, min_sup=min_sup)[:MAX_ALERTS_PER_CHECK]:
        labels = [f"{column}={value}" for column, value in zip(dimensions, cuboid) if value != tree.star_token]
        if not labels:
            labels = ["all stream records"]
        alerts.append(
            _make_alert(
                message=f"High support StarTree cuboid detected: {', '.join(labels)}",
                support=int(support),
                min_sup=min_sup,
                source="star_tree_cuboid",
            )
        )
    return alerts


def _evaluate_grouped_fallback(records: Sequence[dict[str, str]], min_sup: int) -> list[Alert]:
    """Fallback alert rules based on grouped contact/risk patterns.

    This path is used when StarTree/Cubing output cannot be applied directly.
    It groups stream records by available spatiotemporal fields and triggers
    alerts when group frequency reaches ``min_sup``.
    """

    dimensions = _available_columns(records, PATTERN_COLUMNS)
    if not dimensions:
        return []

    support_counter: Counter[tuple[str, ...]] = Counter()
    risk_sums: dict[tuple[str, ...], dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for record in records:
        key = tuple(str(record.get(column, "")) for column in dimensions)
        support_counter[key] += 1
        for risk_column in RISK_COLUMNS:
            risk_sums[key][risk_column] += _to_float(record.get(risk_column))

    alerts: list[Alert] = []
    for key, support in support_counter.most_common():
        if support < min_sup:
            continue
        labels = ", ".join(f"{column}={value}" for column, value in zip(dimensions, key))
        avg_hcir = risk_sums[key]["hcir"] / support if support else 0.0
        avg_contacts = risk_sums[key]["contacts"] / support if support else 0.0
        alerts.append(
            _make_alert(
                message=(
                    "High-risk contact group detected: "
                    f"{labels}, avg_contacts={avg_contacts:.2f}, avg_hcir={avg_hcir:.2f}"
                ),
                support=int(support),
                min_sup=min_sup,
                source="grouped_fallback",
            )
        )
        if len(alerts) >= MAX_ALERTS_PER_CHECK:
            break

    return alerts


def evaluate_alerts(records: Sequence[dict[str, str]], min_sup: int = MIN_SUP) -> list[Alert]:
    """Compare stream batch support/risk values against ``min_sup``."""

    if min_sup < 1:
        raise ValueError("min_sup must be >= 1")
    if not records:
        return []

    try:
        alerts = _evaluate_with_star_tree(records, min_sup=min_sup)
    except Exception as exc:
        print(f"[alert_system] StarTree/Cubing evaluation unavailable, using grouped fallback: {exc}")
        alerts = []

    if alerts:
        return alerts
    return _evaluate_grouped_fallback(records, min_sup=min_sup)


def write_alert(alert: Alert | str, log_path: Path = ALERT_LOG_PATH) -> None:
    """Print an alert message and append it to ``alerts.log``."""

    line = alert.format() if isinstance(alert, Alert) else str(alert)
    print(line)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")


def run_alert_loop(
    min_sup: int = MIN_SUP,
    check_interval_seconds: int = CHECK_INTERVAL_SECONDS,
    stream_batch_size: int = STREAM_BATCH_SIZE,
    alert_log_path: Path = ALERT_LOG_PATH,
    data_path: Path = STREAM_DATA_PATH,
    max_checks: int | None = 1,
) -> None:
    """Run scheduled stream checks as a simple local scheduler loop."""

    check_count = 0
    offset: int | None = None

    while max_checks is None or check_count < max_checks:
        records = load_stream_batch(data_path=data_path, batch_size=stream_batch_size, offset=offset)
        if not records:
            write_alert(
                f"{datetime.now().isoformat(timespec='seconds')} [INFO] No stream records available for alert check.",
                log_path=alert_log_path,
            )
        else:
            alerts = evaluate_alerts(records, min_sup=min_sup)
            if alerts:
                for alert in alerts:
                    write_alert(alert, log_path=alert_log_path)
            else:
                write_alert(
                    f"{datetime.now().isoformat(timespec='seconds')} [INFO] No alerts triggered for batch_size={len(records)}, min_sup={min_sup}.",
                    log_path=alert_log_path,
                )

        check_count += 1
        if max_checks is not None and check_count >= max_checks:
            break

        offset = 0 if offset is None else offset + stream_batch_size
        time.sleep(check_interval_seconds)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Task 14 stream-like outbreak alert checks.")
    parser.add_argument("--min-sup", type=int, default=MIN_SUP, help="Minimum support threshold for alerts.")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL_SECONDS, help="Seconds between loop checks.")
    parser.add_argument("--batch-size", type=int, default=STREAM_BATCH_SIZE, help="Number of records per stream batch.")
    parser.add_argument("--log-path", type=Path, default=ALERT_LOG_PATH, help="Path to append alert messages.")
    parser.add_argument("--data-path", type=Path, default=STREAM_DATA_PATH, help="Processed dataset used as stream source.")
    parser.add_argument("--loop", action="store_true", help="Run continuously until interrupted.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_alert_loop(
        min_sup=args.min_sup,
        check_interval_seconds=args.interval,
        stream_batch_size=args.batch_size,
        alert_log_path=args.log_path,
        data_path=args.data_path,
        max_checks=None if args.loop else 1,
    )


if __name__ == "__main__":
    main()
