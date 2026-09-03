from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from uuid import UUID


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ArtifactValidationError(RuntimeError):
    pass


def canonical_uuid(value: str) -> str:
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError("simulation_id must be a canonical UUID")
    return value


def contained_child(root: Path, name: str) -> Path:
    root = root.resolve()
    child = (root / name).resolve()
    try:
        child.relative_to(root)
    except ValueError as exc:
        raise ValueError("resolved path escapes the configured results root") from exc
    return child


def prepare_staging_directory(results_root: Path, simulation_id: str) -> tuple[Path, Path]:
    canonical_uuid(simulation_id)
    results_root = results_root.resolve()
    results_root.mkdir(parents=True, exist_ok=True)
    final_dir = contained_child(results_root, simulation_id)
    staging_dir = contained_child(results_root, f".{simulation_id}.staging")
    if final_dir.exists() or staging_dir.exists():
        raise FileExistsError("result directory already exists")
    staging_dir.mkdir(parents=False)
    return staging_dir, final_dir


def atomic_write_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)


def validate_png(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= len(PNG_SIGNATURE):
        raise ArtifactValidationError(f"missing or empty PNG: {path.name}")
    with path.open("rb") as handle:
        if handle.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
            raise ArtifactValidationError(f"invalid PNG signature: {path.name}")


def validate_mp4(path: Path, expected_duration: float | None = None) -> float | None:
    if not path.is_file() or path.stat().st_size <= 12:
        raise ArtifactValidationError(f"missing or empty MP4: {path.name}")
    with path.open("rb") as handle:
        header = handle.read(12)
    if header[4:8] != b"ftyp":
        raise ArtifactValidationError(f"invalid MP4 container signature: {path.name}")

    duration = expected_duration
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        duration = float(completed.stdout.strip())

    if duration is None or duration <= 0:
        raise ArtifactValidationError("MP4 duration was not positively verified")
    return duration
