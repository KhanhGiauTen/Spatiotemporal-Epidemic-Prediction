"""Tests for the reusable Pandas ETL pipeline."""

from __future__ import annotations

import unittest

import pandas as pd

from scripts.etl import run_etl


def sample_metadata() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "indid": "P001",
                "site": "Soweto",
                "agegrp9": "18-34",
                "sex": "Female",
                "ind_inc_ana": "Yes",
                "hhid": "H001",
                "smokecignow1": "No",
                "bmicat": "Normal weight",
                "ixagegrp9": None,
                "ixsex": None,
                "ixminctcat1": None,
                "ixminctcat2": None,
                "sleep_room_ix": "Unknown",
                "cared_by_ix": "No",
                "sus": None,
                "ixesarsvarf1": None,
                "index": "Index",
                "sars": "Positive",
            },
            {
                "indid": "P002",
                "site": "Soweto",
                "agegrp9": "12-May",
                "sex": "Male",
                "ind_inc_ana": "Yes",
                "hhid": "H001",
                "smokecignow1": "Yes",
                "bmicat": "Overweight",
                "ixagegrp9": "18-34",
                "ixsex": "Female",
                "ixminctcat1": "<25",
                "ixminctcat2": "<30",
                "sleep_room_ix": "No",
                "cared_by_ix": "No",
                "sus": "Susceptible",
                "ixesarsvarf1": "Beta",
                "index": "Contact",
                "sars": "Negative",
            },
        ]
    )


def sample_network() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "t": "2021-01-01 00:00:00",
                "duration_sec": 40,
                "indid1": "P001",
                "indid2": "P002",
                "date": "2021-01-01",
                "pair": "P001_P002",
                "hh": "H001",
                "deployed1": "",
                "collected1": "",
                "deployed2": "",
                "collected2": "",
                "no_ts": 1,
                "sars_indid1": "Positive",
                "age_indid1": "18-34",
                "sars_indid2": "Negative",
                "age_indid2": "5-12",
                "contacts": 2,
                "contacts_infected": 1,
                "hcir": 50,
                "hh_ar": 60,
                "pair_sars": "Transmission",
            }
        ]
    )


class TestEtlPipeline(unittest.TestCase):
    def test_run_etl_outputs_processed_dataset_and_mapping(self):
        outputs = run_etl(sample_metadata(), sample_network(), save_artifacts=False)

        self.assertEqual(len(outputs["df_result"]), 1)
        self.assertIn("month_id", outputs["df_result"].columns)
        self.assertIn("pair_sars", outputs["mapping_dict"])
        self.assertEqual(outputs["df_meta_cleaned"].loc[1, "agegrp9"], "5-12")
        self.assertEqual(outputs["validation_report"]["network_row_count"], 1)

    def test_run_etl_rejects_missing_required_columns(self):
        metadata = sample_metadata().drop(columns=["indid"])
        with self.assertRaises(ValueError):
            run_etl(metadata, sample_network(), save_artifacts=False)


if __name__ == "__main__":
    unittest.main()
