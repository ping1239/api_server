from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from services.result_parser import parse_kpis
from services.storage import contained_child, prepare_staging_directory


def test_containment_rejects_parent_escape(tmp_path):
    with pytest.raises(ValueError):
        contained_child(tmp_path, "../outside")


def test_staging_path_is_contained_and_uuid_named(tmp_path):
    simulation_id = str(uuid4())
    staging, final = prepare_staging_directory(tmp_path, simulation_id)
    assert staging.parent == tmp_path.resolve()
    assert final == tmp_path.resolve() / simulation_id


def test_kpis_are_parsed_from_source_and_field_metadata(tmp_path):
    source = tmp_path / "source.json"
    fields = tmp_path / "fields.json"
    source.write_text(
        json.dumps(
            {
                "fill_fraction": 0.98006144,
                "fill_time_s": 0.4078242678,
                "max_pressure_mpa": 20.0,
                "mesh_cells": 232123,
            }
        ),
        encoding="utf-8",
    )
    fields.write_text(
        json.dumps(
            {
                "max_pressure_mpa": 21.10211,
                "min_temperature_c": 68.2700134277344,
                "max_temperature_c": 227.89202270507815,
                "max_shear_rate_1_s": 3096.970458984375,
            }
        ),
        encoding="utf-8",
    )
    summary = parse_kpis(source, fields)
    assert summary["fill_fraction"] == pytest.approx(0.98006144)
    assert summary["fill_time_s"] == pytest.approx(0.4078242678)
    assert summary["max_pressure_mpa"] == pytest.approx(21.10211)
    assert summary["mesh_cells"] == 232123
    assert summary["unavailable_reasons"] == {}


def test_unavailable_kpis_are_null_with_reasons(tmp_path):
    source = tmp_path / "source.json"
    fields = tmp_path / "fields.json"
    source.write_text("{}", encoding="utf-8")
    fields.write_text("{}", encoding="utf-8")
    summary = parse_kpis(source, fields)
    assert summary["fill_fraction"] is None
    assert "fill_fraction" in summary["unavailable_reasons"]
    assert summary["max_pressure_mpa"] is None
    assert "max_pressure_mpa" in summary["unavailable_reasons"]
