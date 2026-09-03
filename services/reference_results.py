from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Callable

from settings import (
    POST_PROCESS_TIMEOUT_SECONDS,
    PROJECT_ROOT,
    REFERENCE_CASES,
    wsl_distribution,
    wsl_runtime_root,
)
from services.result_parser import parse_kpis
from services.storage import (
    ArtifactValidationError,
    atomic_write_json,
    prepare_staging_directory,
    validate_mp4,
    validate_png,
)


class ResultProcessingError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


ARTIFACT_MAP = {
    "fill_final": ("final/fill_final.png", "fill_final.png"),
    "fill_animation": ("animations/fill_animation.mp4", "fill_animation.mp4"),
    "pressure_final": ("final/pressure_final.png", "pressure_final.png"),
    "temperature_final": ("final/temperature_final.png", "temperature_final.png"),
    "shear_rate_final": ("final/shear_rate_final.png", "shear_rate_final.png"),
}


def _run(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd="C:\\",
    )


def _script_wsl_path(script: Path, distribution: str) -> str:
    converted = _run(
        ["wsl.exe", "-d", distribution, "--", "wslpath", "-a", "-u", str(script)],
        timeout=30,
    )
    path = converted.stdout.strip()
    if not path.startswith("/"):
        raise ResultProcessingError("WSL_PATH_ERROR", "Could not resolve the WSL script path")
    return path


def _windows_wsl_path(distribution: str, linux_path: str) -> Path:
    parts = PurePosixPath(linux_path).parts
    if not parts or parts[0] != "/":
        raise ResultProcessingError("WSL_PATH_ERROR", "WSL result path is not absolute")
    result = Path(f"\\\\wsl.localhost\\{distribution}")
    for part in parts[1:]:
        result /= part
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def process_reference_result(
    *,
    simulation_id: str,
    reference_case: str,
    results_root: Path,
    on_validating: Callable[[], None],
) -> dict:
    if reference_case not in REFERENCE_CASES:
        raise ResultProcessingError("UNSUPPORTED_REFERENCE_CASE", "Unsupported reference case")

    try:
        staging_dir, final_dir = prepare_staging_directory(results_root, simulation_id)
    except (ValueError, FileExistsError) as exc:
        raise ResultProcessingError("UNSAFE_RESULT_PATH", str(exc)) from exc

    distribution = wsl_distribution()
    runtime_root = wsl_runtime_root().rstrip("/")
    runtime_dir = f"{runtime_root}/{simulation_id}"
    wrapper = PROJECT_ROOT / "scripts" / "process_reference_result.sh"

    try:
        wrapper_wsl = _script_wsl_path(wrapper, distribution)
        completed = _run(
            [
                "wsl.exe",
                "-d",
                distribution,
                "--",
                "env",
                f"RMS_WSL_RUNTIME_ROOT={runtime_root}",
                "bash",
                wrapper_wsl,
                simulation_id,
                reference_case,
            ],
            timeout=POST_PROCESS_TIMEOUT_SECONDS,
        )
        (staging_dir / "postprocess.log").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
    except subprocess.TimeoutExpired as exc:
        raise ResultProcessingError(
            "POST_PROCESS_TIMEOUT", "Reference post-processing exceeded its time limit"
        ) from exc
    except subprocess.CalledProcessError as exc:
        log = (exc.stdout or "") + (exc.stderr or "")
        (staging_dir / "postprocess.log").write_text(log, encoding="utf-8")
        raise ResultProcessingError(
            "POST_PROCESS_COMMAND_FAILED",
            "WSL reference post-processing failed; inspect the server-side job log",
        ) from exc

    on_validating()
    output_dir = _windows_wsl_path(distribution, f"{runtime_dir}/output")

    try:
        copied: dict[str, Path] = {}
        for public_name, (relative_source, destination_name) in ARTIFACT_MAP.items():
            source = output_dir / Path(relative_source)
            if not source.is_file():
                raise ArtifactValidationError(f"missing WSL artifact: {relative_source}")
            destination = staging_dir / destination_name
            shutil.copy2(source, destination)
            copied[public_name] = destination

        for metadata_name in ("source_kpis.json", "field_metrics.json"):
            source = output_dir / metadata_name
            if not source.is_file():
                raise ArtifactValidationError(f"missing metadata: {metadata_name}")
            shutil.copy2(source, staging_dir / metadata_name)

        validate_png(copied["fill_final"])
        validate_png(copied["pressure_final"])
        validate_png(copied["temperature_final"])
        validate_png(copied["shear_rate_final"])

        media_probe = json.loads((output_dir / "media_probe.json").read_text(encoding="utf-8"))
        expected_duration = float(media_probe["fill_animation_duration_s"])
        duration = validate_mp4(copied["fill_animation"], expected_duration)

        summary = parse_kpis(
            staging_dir / "source_kpis.json", staging_dir / "field_metrics.json"
        )
    except (ArtifactValidationError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ResultProcessingError("RESULT_VALIDATION_FAILED", str(exc)) from exc

    public_artifacts = {
        name: f"/results/{simulation_id}/{path.name}" for name, path in copied.items()
    }
    manifest = {
        "simulation_id": simulation_id,
        "execution_mode": "reference_result",
        "reference_case": reference_case,
        "source_case_path": REFERENCE_CASES[reference_case],
        "wsl_work_directory": runtime_dir,
        "alpha_threshold": 0.5,
        "kpis": summary,
        "artifacts": {
            name: {
                "filename": path.name,
                "url": public_artifacts[name],
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for name, path in copied.items()
        },
        "media": {"fill_animation_duration_s": duration},
    }
    atomic_write_json(staging_dir / "manifest.json", manifest)

    # The directory becomes publicly visible only after every validation succeeds.
    staging_dir.rename(final_dir)
    return {
        "simulation_id": simulation_id,
        "execution_mode": "reference_result",
        "reference_case": reference_case,
        "summary": summary,
        "artifacts": public_artifacts,
        "heatmaps": {
            "fill": public_artifacts["fill_final"],
            "pressure": public_artifacts["pressure_final"],
            "temperature": public_artifacts["temperature_final"],
            "shear_rate": public_artifacts["shear_rate_final"],
        },
        "animations": {"fill": public_artifacts["fill_animation"]},
    }
