"""Integration tests for the DuckDB warehouse pipeline."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

import duckdb

from scripts.etl_tests import sample_metadata, sample_network
from scripts.run_pipeline import run_pipeline


class TestRunPipeline(unittest.TestCase):
    def test_duckdb_pipeline_creates_dw_and_powerbi_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "raw").mkdir(parents=True)
            sample_metadata().to_csv(root / "data" / "raw" / "sashts_metadata.csv", index=False)
            sample_network().to_csv(root / "data" / "raw" / "sashts_contact_network.csv", index=False)

            args = argparse.Namespace(
                project_root=str(root),
                metadata_path="data/raw/sashts_metadata.csv",
                network_path="data/raw/sashts_contact_network.csv",
                processed_dir="data/processed",
                reports_dir="reports",
                dw="duckdb",
                duckdb_path="warehouse/epidemic.duckdb",
                database_url=None,
                refresh=True,
                threshold=1,
                min_sup=1,
                run_id="test-run",
                cube_dimensions=["month_id", "ind1_site", "ind2_site", "pair_sars"],
            )

            summary = run_pipeline(args)

            db_path = root / "warehouse" / "epidemic.duckdb"
            self.assertTrue(db_path.exists())
            self.assertEqual(summary["load_summary"]["exposure_records"], 1)
            self.assertGreaterEqual(summary["iceberg_cuboids"], 1)
            self.assertTrue((root / "powerbi" / "data" / "overview_kpis.csv").exists())

            conn = duckdb.connect(str(db_path), read_only=True)
            try:
                exposure_count = conn.execute('SELECT COUNT(*) FROM "Fact_Exposure"').fetchone()[0]
                cuboid_count = conn.execute('SELECT COUNT(*) FROM "Fact_Iceberg_Cuboid"').fetchone()[0]
            finally:
                conn.close()

            self.assertEqual(exposure_count, 1)
            self.assertGreaterEqual(cuboid_count, 1)


if __name__ == "__main__":
    unittest.main()
