from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from services.reference_results import ResultProcessingError


def _replace_state(
    db: dict,
    lock: threading.Lock,
    simulation_id: str,
    **changes: object,
) -> None:
    with lock:
        current = dict(db[simulation_id])
        current.update(changes)
        db[simulation_id] = current


def run_reference_result_job(
    simulation_id: str,
    config: dict,
    db: dict,
    lock: threading.Lock,
    results_dir: Path,
    processor: Callable[..., dict],
) -> None:
    """Post-process a completed case. This function never launches a solver or mesher."""
    failed_stage = "POST_PROCESSING"
    try:
        _replace_state(
            db,
            lock,
            simulation_id,
            status="POST_PROCESSING",
            stage="POST_PROCESSING",
            progress=55,
        )

        def mark_validating() -> None:
            nonlocal failed_stage
            failed_stage = "VALIDATING_RESULTS"
            _replace_state(
                db,
                lock,
                simulation_id,
                status="VALIDATING_RESULTS",
                stage="VALIDATING_RESULTS",
                progress=85,
            )

        results = processor(
            simulation_id=simulation_id,
            reference_case=config["reference_case"],
            results_root=results_dir,
            on_validating=mark_validating,
        )

        # COMPLETED is deliberately the final, single state replacement.
        _replace_state(
            db,
            lock,
            simulation_id,
            status="COMPLETED",
            stage="COMPLETED",
            progress=100,
            results=results,
            error=None,
        )
    except ResultProcessingError as exc:
        _replace_state(
            db,
            lock,
            simulation_id,
            status="FAILED",
            stage=failed_stage,
            error={"error_code": exc.error_code, "message": str(exc)},
        )
    except Exception:
        _replace_state(
            db,
            lock,
            simulation_id,
            status="FAILED",
            stage=failed_stage,
            error={
                "error_code": "INTERNAL_POST_PROCESSING_ERROR",
                "message": "Unexpected post-processing failure",
            },
        )
