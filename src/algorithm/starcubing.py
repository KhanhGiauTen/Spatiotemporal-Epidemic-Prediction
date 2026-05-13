"""Export Star-Cubing results from RAM into Data Warehouse fact records."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

try:
    from ..db_manager import DatabaseManager, DimLocation, DimPatient, DimTime
except Exception:  # pragma: no cover - fallback for direct script execution
    from db_manager import DatabaseManager, DimLocation, DimPatient, DimTime


CubeRecord = Union[
    Dict[str, Any],
    Tuple[Sequence[Any], int],
    Sequence[Any],
]


def _load_mapping_dict(
    mapping_dict: Optional[Mapping[str, Mapping[str, int]]] = None,
    mapping_dict_path: Union[str, Path] = "data/processed/mapping_dict.json",
) -> Dict[str, Dict[str, int]]:
    if mapping_dict is not None:
        return {k: dict(v) for k, v in mapping_dict.items()}

    mapping_file = Path(mapping_dict_path)
    if not mapping_file.exists():
        return {}

    with mapping_file.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    return {k: dict(v) for k, v in loaded.items()}


def _invert_mapping(mapping_dict: Mapping[str, Mapping[str, int]]) -> Dict[str, Dict[int, str]]:
    inverse: Dict[str, Dict[int, str]] = {}
    for col, col_map in mapping_dict.items():
        inverse[col] = {int(code): str(label) for label, code in col_map.items()}
    return inverse


def _record_to_dict(record: CubeRecord, columns: Optional[Sequence[str]]) -> Dict[str, Any]:
    if isinstance(record, dict):
        return dict(record)

    if isinstance(record, tuple) and len(record) == 2 and isinstance(record[1], int):
        values, support = record
        if columns is None:
            raise ValueError("columns is required when cube records are value vectors")
        if len(values) != len(columns):
            raise ValueError("record length does not match columns length")
        out = dict(zip(columns, values))
        out.setdefault("count_exposure", int(support))
        return out

    if columns is None:
        raise ValueError("columns is required when cube records are not dictionaries")
    if len(record) != len(columns):
        raise ValueError("record length does not match columns length")
    return dict(zip(columns, record))


def _decode_row(row: Dict[str, Any], inverse_mapping: Mapping[str, Mapping[int, str]]) -> Dict[str, Any]:
    decoded = dict(row)
    for col, inv_map in inverse_mapping.items():
        if col not in decoded:
            continue
        value = decoded[col]
        if isinstance(value, (int, float)):
            as_int = int(value)
            if as_int in inv_map:
                decoded[col] = inv_map[as_int]
    return decoded


def _build_time_indexes(session) -> Tuple[Dict[str, int], Dict[Tuple[int, int], int]]:
    by_date: Dict[str, int] = {}
    by_year_month: Dict[Tuple[int, int], int] = {}

    rows = session.query(DimTime.time_id, DimTime.date_full, DimTime.year, DimTime.month).all()
    for time_id, date_full, year, month in rows:
        if isinstance(date_full, date):
            key = date_full.isoformat()
            by_date[key] = int(time_id)
        ym = (int(year), int(month))
        existing = by_year_month.get(ym)
        if existing is None or int(time_id) < existing:
            by_year_month[ym] = int(time_id)

    return by_date, by_year_month


def _build_location_indexes(session) -> Tuple[Dict[str, int], Dict[Tuple[str, str], int]]:
    by_site: Dict[str, int] = {}
    by_lat_long: Dict[Tuple[str, str], int] = {}

    rows = session.query(DimLocation.location_id, DimLocation.site_name, DimLocation.latitude, DimLocation.longitude).all()
    for location_id, site_name, latitude, longitude in rows:
        if site_name is not None:
            by_site[str(site_name)] = int(location_id)
        if latitude is not None and longitude is not None:
            by_lat_long[(str(latitude), str(longitude))] = int(location_id)

    return by_site, by_lat_long


def _build_patient_index(session) -> Dict[str, int]:
    by_code: Dict[str, int] = {}
    rows = session.query(DimPatient.patient_id, DimPatient.patient_code).all()
    for patient_id, patient_code in rows:
        by_code[str(patient_code)] = int(patient_id)
    return by_code


def _resolve_time_id(
    row: Mapping[str, Any],
    by_date: Mapping[str, int],
    by_year_month: Mapping[Tuple[int, int], int],
) -> Optional[int]:
    if "time_id" in row and row["time_id"] is not None:
        return int(row["time_id"])

    if "date" in row and row["date"] is not None:
        date_text = str(row["date"])
        try:
            parsed = datetime.fromisoformat(date_text).date().isoformat()
        except ValueError:
            parsed = date_text
        if parsed in by_date:
            return by_date[parsed]

    if "time" in row and row["time"] is not None:
        time_text = str(row["time"])
        try:
            parsed = datetime.fromisoformat(time_text).date().isoformat()
            if parsed in by_date:
                return by_date[parsed]
        except ValueError:
            pass

    if "month_id" in row and row["month_id"] is not None:
        month_id = int(row["month_id"])
        year = month_id // 100
        month = month_id % 100
        return by_year_month.get((year, month))

    return None


def _resolve_location_id(
    row: Mapping[str, Any],
    by_site: Mapping[str, int],
    by_lat_long: Mapping[Tuple[str, str], int],
) -> Optional[int]:
    if "location_id" in row and row["location_id"] is not None:
        return int(row["location_id"])

    for site_key in ("site", "site_name", "ind1_site", "location"):
        if site_key in row and row[site_key] is not None:
            site = str(row[site_key])
            if site in by_site:
                return by_site[site]

    lat_keys = ("latitude", "lat", "ind1_latitude")
    long_keys = ("longitude", "long", "lng", "ind1_longitude")
    lat_value = next((str(row[k]) for k in lat_keys if k in row and row[k] is not None), None)
    long_value = next((str(row[k]) for k in long_keys if k in row and row[k] is not None), None)
    if lat_value is not None and long_value is not None:
        return by_lat_long.get((lat_value, long_value))

    return None


def _resolve_patient_ids(
    row: Mapping[str, Any],
    patient_by_code: Mapping[str, int],
    default_patient_id: Optional[int],
    default_contact_patient_id: Optional[int],
) -> Tuple[Optional[int], Optional[int]]:
    patient_id: Optional[int] = None
    contact_id: Optional[int] = None

    if row.get("patient_id") is not None:
        patient_id = int(row["patient_id"])
    elif row.get("indid1") is not None:
        patient_id = patient_by_code.get(str(row["indid1"]))
    elif row.get("patient_code") is not None:
        patient_id = patient_by_code.get(str(row["patient_code"]))
    else:
        patient_id = default_patient_id

    if row.get("contact_patient_id") is not None:
        contact_id = int(row["contact_patient_id"])
    elif row.get("indid2") is not None:
        contact_id = patient_by_code.get(str(row["indid2"]))
    elif row.get("contact_code") is not None:
        contact_id = patient_by_code.get(str(row["contact_code"]))
    else:
        contact_id = default_contact_patient_id

    return patient_id, contact_id


def export_cube_to_sql(
    cube_records: Iterable[CubeRecord],
    db_manager: DatabaseManager,
    session=None,
    columns: Optional[Sequence[str]] = None,
    mapping_dict: Optional[Mapping[str, Mapping[str, int]]] = None,
    mapping_dict_path: Union[str, Path] = "data/processed/mapping_dict.json",
    batch_size: int = 1000,
    strict: bool = False,
    default_patient_id: Optional[int] = None,
    default_contact_patient_id: Optional[int] = None,
) -> Dict[str, int]:
    """
    Export in-memory cube rows into Fact_Exposure with batch insert.

    Supports reverse mapping for integer-encoded dimensions from Task 4 mapping dictionary.
    The function resolves `time_id` and `location_id` from decoded values (time/month_id/lat/long/site).
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    owned_session = session is None
    session = db_manager.get_session() if owned_session else session

    try:
        loaded_mapping = _load_mapping_dict(mapping_dict=mapping_dict, mapping_dict_path=mapping_dict_path)
        inverse_mapping = _invert_mapping(loaded_mapping)

        by_date, by_year_month = _build_time_indexes(session)
        by_site, by_lat_long = _build_location_indexes(session)
        patient_by_code = _build_patient_index(session)

        prepared_records: List[Dict[str, Any]] = []
        skipped = 0
        input_records = 0

        for item in cube_records:
            input_records += 1
            row = _record_to_dict(item, columns=columns)
            decoded = _decode_row(row, inverse_mapping)

            time_id = _resolve_time_id(decoded, by_date=by_date, by_year_month=by_year_month)
            location_id = _resolve_location_id(decoded, by_site=by_site, by_lat_long=by_lat_long)
            patient_id, contact_id = _resolve_patient_ids(
                decoded,
                patient_by_code=patient_by_code,
                default_patient_id=default_patient_id,
                default_contact_patient_id=default_contact_patient_id,
            )

            count_exposure = int(decoded.get("count_exposure", decoded.get("support", 1)))

            if time_id is None or location_id is None or patient_id is None:
                if strict:
                    raise ValueError(
                        f"Unable to resolve required keys for row: time_id={time_id}, "
                        f"location_id={location_id}, patient_id={patient_id}, row={decoded}"
                    )
                skipped += 1
                continue

            fact_record: Dict[str, Any] = {
                "time_id": int(time_id),
                "location_id": int(location_id),
                "patient_id": int(patient_id),
                "contact_patient_id": int(contact_id) if contact_id is not None else None,
                "count_exposure": count_exposure,
                "exposure_strength": decoded.get("exposure_strength"),
                "sars_status_patient": decoded.get("ind1_sars") or decoded.get("sars_status_patient"),
                "susceptibility_status": decoded.get("ind1_sus") or decoded.get("susceptibility_status"),
                "variant_type": decoded.get("ind1_ixesarsvarf1") or decoded.get("variant_type"),
                "contact_duration_category": decoded.get("contact_duration_category"),
                "is_threshold_exceeded": bool(decoded.get("is_threshold_exceeded", True)),
            }
            prepared_records.append(fact_record)

        inserted = 0
        for idx in range(0, len(prepared_records), batch_size):
            chunk = prepared_records[idx : idx + batch_size]
            if not chunk:
                continue
            inserted += int(db_manager.insert_exposure_fact(session, chunk))

        return {
            "input_records": input_records,
            "prepared_records": len(prepared_records),
            "inserted_records": inserted,
            "skipped_records": skipped,
            "batch_size": batch_size,
        }
    finally:
        if owned_session:
            session.close()
