from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest

from services.reference_results import process_reference_result


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RMS_RUN_INTEGRATION") != "1",
    reason="set RMS_RUN_INTEGRATION=1 to run real WSL ParaView processing",
)
def test_real_dogbone_reference_pipeline(tmp_path):
    simulation_id = str(uuid4())
    stages = []
    result = process_reference_result(
        simulation_id=simulation_id,
        reference_case="dogbone",
        results_root=tmp_path / "results",
        on_validating=lambda: stages.append("VALIDATING_RESULTS"),
    )

    assert stages == ["VALIDATING_RESULTS"]
    assert result["summary"]["fill_fraction"] == pytest.approx(0.98006144, abs=1e-8)
    assert result["summary"]["fill_time_s"] == pytest.approx(0.4078242678, abs=1e-10)
    assert result["summary"]["max_pressure_mpa"] == pytest.approx(21.10211, rel=1e-4)
    assert result["summary"]["mesh_cells"] == 232123

    result_dir = tmp_path / "results" / simulation_id
    for filename in (
        "fill_final.png",
        "fill_animation.mp4",
        "pressure_final.png",
        "temperature_final.png",
        "shear_rate_final.png",
        "manifest.json",
    ):
        path = result_dir / filename
        assert path.is_file()
        assert path.stat().st_size > 0

    assert (result_dir / "fill_final.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    manifest = json.loads((result_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["simulation_id"] == simulation_id
    assert manifest["execution_mode"] == "reference_result"
    assert manifest["kpis"]["mesh_cells"] == 232123
    assert manifest["artifacts"]["fill_animation"]["url"].endswith(
        "/fill_animation.mp4"
    )
