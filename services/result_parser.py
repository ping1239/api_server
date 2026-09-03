from __future__ import annotations

import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _number(payload: dict, key: str) -> float | int | None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def parse_kpis(source_path: Path, field_path: Path) -> dict:
    source = _load_json(source_path)
    fields = _load_json(field_path)
    unavailable: dict[str, str] = {}

    def value_or_reason(
        key: str,
        primary: dict,
        primary_key: str,
        reason: str,
    ) -> float | int | None:
        value = _number(primary, primary_key)
        if value is None:
            unavailable[key] = reason
        return value

    fill_fraction = value_or_reason(
        "fill_fraction",
        source,
        "fill_fraction",
        "No liquid phase volume fraction was found in the solver log.",
    )
    fill_percent = fill_fraction * 100.0 if fill_fraction is not None else None
    fill_time = value_or_reason(
        "fill_time_s", source, "fill_time_s", "No physical time was found."
    )
    mesh_cells = value_or_reason(
        "mesh_cells", source, "mesh_cells", "No cell count was found in checkMesh output."
    )

    max_pressure = _number(fields, "max_pressure_mpa")
    if max_pressure is None:
        max_pressure = _number(source, "max_pressure_mpa")
    if max_pressure is None:
        unavailable["max_pressure_mpa"] = "Pressure was unavailable in fields and logs."

    min_temperature = value_or_reason(
        "min_temperature_c",
        fields,
        "min_temperature_c",
        "Temperature was not available in the filled polymer region.",
    )
    max_temperature = value_or_reason(
        "max_temperature_c",
        fields,
        "max_temperature_c",
        "Temperature was not available in the filled polymer region.",
    )
    max_shear = value_or_reason(
        "max_shear_rate_1_s",
        fields,
        "max_shear_rate_1_s",
        "Shear rate was not available in the filled polymer region.",
    )

    return {
        "fill_fraction": fill_fraction,
        "fill_percent": fill_percent,
        "fill_time_s": fill_time,
        "max_pressure_mpa": max_pressure,
        "min_temperature_c": min_temperature,
        "max_temperature_c": max_temperature,
        "max_shear_rate_1_s": max_shear,
        "mesh_cells": mesh_cells,
        "unavailable_reasons": unavailable,
    }
