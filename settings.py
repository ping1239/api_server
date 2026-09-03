from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def default_results_root() -> Path:
    configured = os.getenv("RMS_RESULTS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (PROJECT_ROOT / "runtime" / "results").resolve()


def wsl_distribution() -> str:
    return os.getenv("RMS_WSL_DISTRIBUTION", "Ubuntu-20.04")


def wsl_runtime_root() -> str:
    return os.getenv("RMS_WSL_RUNTIME_ROOT", "/home/kkwon/rms-api-runtime")


REFERENCE_CASES = {
    "dogbone": "/home/kkwon/rms-injection-sim-cpu/tutorials/demo/dogbone",
}

POST_PROCESS_TIMEOUT_SECONDS = int(os.getenv("RMS_POST_PROCESS_TIMEOUT_SECONDS", "1800"))
