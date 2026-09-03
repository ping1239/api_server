from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from schemas import parse_reference_config
from settings import default_results_root
from services.reference_results import process_reference_result
from services.storage import canonical_uuid, contained_child
from worker_tasks import run_reference_result_job


Processor = Callable[..., dict]
PUBLIC_ARTIFACTS = {
    "fill_final.png",
    "fill_animation.mp4",
    "pressure_final.png",
    "temperature_final.png",
    "shear_rate_final.png",
}


def create_app(
    *,
    results_dir: Path | None = None,
    processor: Processor = process_reference_result,
) -> FastAPI:
    """Create the API app; injectable paths/processors keep tests isolated."""
    app = FastAPI(title="RMS OpenFOAM Reference Result API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://192.168.0.79:5174", "http://localhost:5174"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    result_root = (results_dir or default_results_root()).resolve()
    result_root.mkdir(parents=True, exist_ok=True)
    app.state.results_dir = result_root
    app.state.job_status_db = {}
    app.state.job_lock = threading.Lock()
    app.state.processor = processor

    @app.get("/results/{simulation_id}/{filename}", name="result_artifact")
    async def get_result_artifact(simulation_id: str, filename: str) -> FileResponse:
        try:
            canonical_uuid(simulation_id)
            if filename not in PUBLIC_ARTIFACTS:
                raise ValueError("artifact is not public")
            job_dir = contained_child(result_root, simulation_id)
            artifact = contained_child(job_dir, filename)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Result artifact not found") from exc
        if not artifact.is_file():
            raise HTTPException(status_code=404, detail="Result artifact not found")
        return FileResponse(artifact)

    @app.post("/api/simulate", status_code=202)
    async def start_simulation(
        background_tasks: BackgroundTasks,
        config_json: str = Form(...),
        stl_file: UploadFile | None = File(default=None),
    ) -> dict:
        config = parse_reference_config(config_json)

        # Reference mode deliberately does not persist or inspect STL data.
        if stl_file is not None:
            await stl_file.close()

        simulation_id = str(uuid4())
        initial_state = {
            "simulation_id": simulation_id,
            "client_job_id": config.client_job_id,
            "execution_mode": config.mode,
            "reference_case": config.reference_case,
            "uploaded_stl_used": False,
            "status": "REFERENCE_SELECTED",
            "stage": "REFERENCE_SELECTED",
            "progress": 10,
            "results": None,
            "error": None,
        }
        with app.state.job_lock:
            app.state.job_status_db[simulation_id] = initial_state

        background_tasks.add_task(
            run_reference_result_job,
            simulation_id,
            config.model_dump(),
            app.state.job_status_db,
            app.state.job_lock,
            app.state.results_dir,
            app.state.processor,
        )

        return initial_state

    @app.get("/api/simulation/status/{simulation_id}")
    @app.get("/api/status/{simulation_id}", include_in_schema=False)
    async def get_status(simulation_id: str) -> dict:
        with app.state.job_lock:
            status = app.state.job_status_db.get(simulation_id)
            if status is None:
                raise HTTPException(status_code=404, detail="Simulation not found")
            return dict(status)

    @app.get("/")
    async def root() -> dict:
        return {
            "message": "RMS OpenFOAM reference-result API is running.",
            "mode": "reference_result",
        }

    return app


app = create_app()
