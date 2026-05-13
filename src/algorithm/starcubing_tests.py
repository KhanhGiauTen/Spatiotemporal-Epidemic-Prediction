"""Unit tests for cube export to SQL batch loader."""

from __future__ import annotations

import unittest
from datetime import date

try:
    from .starcubing import export_cube_to_sql
except Exception:
    from starcubing import export_cube_to_sql


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self):
        self.closed = False

    def query(self, *args):
        keys = tuple(getattr(arg, "key", str(arg)) for arg in args)

        if keys == ("time_id", "date_full", "year", "month"):
            return FakeQuery([
                (20210101, date(2021, 1, 1), 2021, 1),
                (20210201, date(2021, 2, 1), 2021, 2),
            ])

        if keys == ("location_id", "site_name", "latitude", "longitude"):
            return FakeQuery([
                (7, "Soweto", "-26.2678", "27.8585"),
                (8, "Klerksdorp", "-26.8521", "26.6667"),
            ])

        if keys == ("patient_id", "patient_code"):
            return FakeQuery([
                (101, "P001"),
                (202, "P002"),
            ])

        raise AssertionError(f"Unexpected query keys: {keys}")

    def close(self):
        self.closed = True


class FakeDBManager:
    def __init__(self):
        self.session = FakeSession()
        self.insert_calls = []

    def get_session(self):
        return self.session

    def insert_exposure_fact(self, session, exposure_records):
        self.insert_calls.append(list(exposure_records))
        return len(exposure_records)


class TestExportCubeToSql(unittest.TestCase):
    def test_reverse_mapping_and_key_resolution(self):
        db_manager = FakeDBManager()
        records = [
            {
                "ind1_site": 1,
                "month_id": 202101,
                "patient_code": "P001",
                "count_exposure": 6,
                "ind1_sars": 1,
                "ind1_sus": 1,
                "ind1_ixesarsvarf1": 4,
            }
        ]
        mapping_dict = {
            "ind1_site": {"Klerksdorp": 0, "Soweto": 1},
            "ind1_sars": {"Negative": 0, "Positive": 1},
            "ind1_sus": {"Self Index": 0, "Susceptible": 1},
            "ind1_ixesarsvarf1": {"Self Index": 3, "Variant Unknown": 4},
        }

        summary = export_cube_to_sql(
            cube_records=records,
            db_manager=db_manager,
            mapping_dict=mapping_dict,
            default_contact_patient_id=202,
            batch_size=1000,
        )

        self.assertEqual(summary["input_records"], 1)
        self.assertEqual(summary["inserted_records"], 1)
        self.assertEqual(len(db_manager.insert_calls), 1)
        inserted = db_manager.insert_calls[0][0]
        self.assertEqual(inserted["time_id"], 20210101)
        self.assertEqual(inserted["location_id"], 7)
        self.assertEqual(inserted["patient_id"], 101)
        self.assertEqual(inserted["contact_patient_id"], 202)
        self.assertEqual(inserted["count_exposure"], 6)
        self.assertEqual(inserted["sars_status_patient"], "Positive")
        self.assertEqual(inserted["susceptibility_status"], "Susceptible")
        self.assertEqual(inserted["variant_type"], "Variant Unknown")
        self.assertTrue(db_manager.session.closed)

    def test_batch_insert_and_skip_unresolved_rows(self):
        db_manager = FakeDBManager()
        records = [
            ([1, 202101, "P001"], 5),
            ([0, 202102, "P002"], 7),
            ([99, 202101, "P001"], 4),
        ]
        columns = ["ind1_site", "month_id", "patient_code"]
        mapping_dict = {
            "ind1_site": {"Klerksdorp": 0, "Soweto": 1},
        }

        summary = export_cube_to_sql(
            cube_records=records,
            columns=columns,
            db_manager=db_manager,
            mapping_dict=mapping_dict,
            batch_size=2,
        )

        self.assertEqual(summary["input_records"], 3)
        self.assertEqual(summary["prepared_records"], 2)
        self.assertEqual(summary["inserted_records"], 2)
        self.assertEqual(summary["skipped_records"], 1)
        self.assertEqual(len(db_manager.insert_calls), 1)
        self.assertEqual(len(db_manager.insert_calls[0]), 2)
        self.assertEqual(db_manager.insert_calls[0][0]["count_exposure"], 5)
        self.assertEqual(db_manager.insert_calls[0][1]["count_exposure"], 7)


if __name__ == "__main__":
    unittest.main()
