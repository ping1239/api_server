from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from main import create_app
from services.reference_results import ResultProcessingError
from worker_tasks import run_reference_result_job


PNG = b"\x89PNG\r\n\x1a\nunit-test-image"
MP4 = b"\x00\x00\x00\x18ftypisomunit-test-video"


def successful_processor(*, simulation_id, reference_case, results_root, on_validating):
    on_validating()
    result_dir = Path(results_root) / simulation_id
    result_dir.mkdir()
    artifacts = {
        "fill_final": "fill_final.png",
        "fill_animation": "fill_animation.mp4",
        "pressure_final": "pressure_final.png",
        "temperature_final": "temperature_final.png",
        "shear_rate_final": "shear_rate_final.png",
    }
    for filename in artifacts.values():
        data = MP4 if filename.endswith(".mp4") else PNG
        (result_dir / filename).write_bytes(data)
    return {
        "simulation_id": simulation_id,
        "execution_mode": "reference_result",
        "reference_case": reference_case,
        "summary": {
            "fill_fraction": 0.98006144,
            "fill_percent": 98.006144,
            "fill_time_s": 0.4078242678,
            "max_pressure_mpa": 21.10211,
            "min_temperature_c": 68.2700134277344,
            "max_temperature_c": 227.89202270507815,
            "max_shear_rate_1_s": 3096.970458984375,
            "mesh_cells": 232123,
            "unavailable_reasons": {},
        },
        "artifacts": {
            name: f"/results/{simulation_id}/{filename}"
            for name, filename in artifacts.items()
        },
        "heatmaps": {
            "fill": f"/results/{simulation_id}/fill_final.png",
            "pressure": f"/results/{simulation_id}/pressure_final.png",
            "temperature": f"/results/{simulation_id}/temperature_final.png",
            "shear_rate": f"/results/{simulation_id}/shear_rate_final.png",
        },
        "animations": {
            "fill": f"/results/{simulation_id}/fill_animation.mp4",
        },
    }


@pytest.fixture
def client(tmp_path):
    app = create_app(results_dir=tmp_path / "results", processor=successful_processor)
    with TestClient(app) as test_client:
        yield test_client


def post_config(client, value, with_stl=False):
    files = None
    if with_stl:
        files = {"stl_file": ("../../unsafe.stl", b"solid ignored", "model/stl")}
    return client.post(
        "/api/simulate",
        data={"config_json": value if isinstance(value, str) else json.dumps(value)},
        files=files,
    )


def valid_config(**changes):
    value = {"mode": "reference_result", "reference_case": "dogbone"}
    value.update(changes)
    return value


def test_valid_request_without_stl_returns_202(client):
    response = post_config(client, valid_config())
    assert response.status_code == 202
    assert response.json()["uploaded_stl_used"] is False


def test_multipart_stl_is_explicitly_ignored(client):
    response = post_config(client, valid_config(), with_stl=True)
    assert response.status_code == 202
    assert response.json()["uploaded_stl_used"] is False


def test_server_generates_canonical_uuid(client):
    response = post_config(client, valid_config(client_job_id="REQ-001"))
    simulation_id = response.json()["simulation_id"]
    assert str(UUID(simulation_id)) == simulation_id
    assert simulation_id != "REQ-001"


def test_client_job_id_is_metadata_only(client):
    response = post_config(client, valid_config(client_job_id="../../outside"))
    simulation_id = response.json()["simulation_id"]
    status = client.get(f"/api/simulation/status/{simulation_id}").json()
    assert status["client_job_id"] == "../../outside"
    assert status["results"]["artifacts"]["fill_final"].startswith(
        f"/results/{simulation_id}/"
    )


def test_status_reaches_completed_with_real_values(client):
    simulation_id = post_config(client, valid_config()).json()["simulation_id"]
    status = client.get(f"/api/simulation/status/{simulation_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "COMPLETED"
    assert status.json()["results"]["summary"]["mesh_cells"] == 232123
    assert status.json()["results"]["heatmaps"]["pressure"].endswith(
        "/pressure_final.png"
    )
    assert status.json()["results"]["animations"]["fill"].endswith(
        "/fill_animation.mp4"
    )


@pytest.mark.parametrize(
    "artifact",
    [
        "fill_final",
        "fill_animation",
        "pressure_final",
        "temperature_final",
        "shear_rate_final",
    ],
)
def test_result_urls_are_http_served(client, artifact):
    simulation_id = post_config(client, valid_config()).json()["simulation_id"]
    status = client.get(f"/api/simulation/status/{simulation_id}").json()
    artifact_url = status["results"]["artifacts"][artifact]
    response = client.get(artifact_url)
    assert response.status_code == 200
    assert response.content


@pytest.mark.parametrize("invalid_json", ["{", "[]", "null", "123", '"text"'])
def test_invalid_or_non_object_json_is_422(client, invalid_json):
    assert post_config(client, invalid_json).status_code == 422


def test_missing_mode_is_422(client):
    assert post_config(client, {"reference_case": "dogbone"}).status_code == 422


def test_unsupported_mode_is_422(client):
    assert post_config(client, valid_config(mode="solver")).status_code == 422


def test_unsupported_reference_case_is_422(client):
    assert post_config(client, valid_config(reference_case="other")).status_code == 422


def test_unknown_fields_are_422(client):
    assert post_config(client, valid_config(webhook_url="http://example.invalid")).status_code == 422


def test_blank_client_job_id_is_422(client):
    assert post_config(client, valid_config(client_job_id="   ")).status_code == 422


def test_missing_simulation_is_404(client):
    response = client.get("/api/simulation/status/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_internal_manifest_is_not_public(client):
    simulation_id = post_config(client, valid_config()).json()["simulation_id"]
    response = client.get(f"/results/{simulation_id}/manifest.json")
    assert response.status_code == 404


def test_result_route_rejects_path_traversal(client):
    simulation_id = post_config(client, valid_config()).json()["simulation_id"]
    response = client.get(f"/results/{simulation_id}/..%2Fmanifest.json")
    assert response.status_code == 404


def test_processor_failure_is_structured(tmp_path):
    def failing_processor(**kwargs):
        raise ResultProcessingError("RENDER_FAILED", "renderer exited")

    app = create_app(results_dir=tmp_path / "results", processor=failing_processor)
    with TestClient(app) as client:
        simulation_id = post_config(client, valid_config()).json()["simulation_id"]
        status = client.get(f"/api/simulation/status/{simulation_id}").json()
    assert status["status"] == "FAILED"
    assert status["stage"] == "POST_PROCESSING"
    assert status["error"] == {
        "error_code": "RENDER_FAILED",
        "message": "renderer exited",
    }


def test_worker_records_required_stage_order(tmp_path):
    import threading

    history = []

    class RecordingDb(dict):
        def __setitem__(self, key, value):
            history.append(value["status"])
            super().__setitem__(key, value)

    simulation_id = "00000000-0000-4000-8000-000000000001"
    db = RecordingDb()
    dict.__setitem__(
        db,
        simulation_id,
        {"status": "REFERENCE_SELECTED", "stage": "REFERENCE_SELECTED"},
    )

    def processor(**kwargs):
        kwargs["on_validating"]()
        return {"simulation_id": simulation_id}

    run_reference_result_job(
        simulation_id,
        {"reference_case": "dogbone"},
        db,
        threading.Lock(),
        tmp_path,
        processor,
    )
    assert history == ["POST_PROCESSING", "VALIDATING_RESULTS", "COMPLETED"]
