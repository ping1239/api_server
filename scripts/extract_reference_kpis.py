#!/usr/bin/env python3
from __future__ import print_function

import json
import os
import re
import sys


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
TIME_RE = re.compile(r"^Time\s*=\s*(%s)\s*$" % NUMBER)
FILL_RE = re.compile(r"Liquid phase volume fraction\s*=\s*(%s)" % NUMBER)
PRESSURE_RE = re.compile(r"\bmax\(p\)\s*=\s*(%s)" % NUMBER)
CELLS_RE = re.compile(r"^\s*cells:\s*(\d+)\s*$")


def scan_solver_log(path):
    latest_time = None
    fill_fraction = None
    max_pressure_pa = None
    with open(path, "r") as handle:
        for line in handle:
            match = TIME_RE.search(line)
            if match:
                latest_time = float(match.group(1))
            match = FILL_RE.search(line)
            if match:
                fill_fraction = float(match.group(1))
            match = PRESSURE_RE.search(line)
            if match:
                value = float(match.group(1))
                if max_pressure_pa is None or value > max_pressure_pa:
                    max_pressure_pa = value
    return latest_time, fill_fraction, max_pressure_pa


def scan_cells(path):
    with open(path, "r") as handle:
        for line in handle:
            match = CELLS_RE.match(line)
            if match:
                return int(match.group(1))
    return None


def main():
    if len(sys.argv) != 3:
        print("Usage: extract_reference_kpis.py CASE_DIR OUTPUT.json", file=sys.stderr)
        return 2

    case_dir = os.path.abspath(sys.argv[1])
    output_path = os.path.abspath(sys.argv[2])
    solver_log = os.path.join(case_dir, "log.openInjMoldSim_fill")
    mesh_log = os.path.join(case_dir, "log.checkMesh")
    if os.path.isfile(solver_log):
        latest_time, fill_fraction, max_pressure_pa = scan_solver_log(solver_log)
    else:
        latest_time, fill_fraction, max_pressure_pa = None, None, None
    mesh_cells = scan_cells(mesh_log) if os.path.isfile(mesh_log) else None
    payload = {
        "fill_fraction": fill_fraction,
        "fill_time_s": latest_time,
        "max_pressure_mpa": (
            max_pressure_pa / 1000000.0 if max_pressure_pa is not None else None
        ),
        "mesh_cells": mesh_cells,
        "sources": {
            "fill_fraction": "log.openInjMoldSim_fill",
            "fill_time_s": "log.openInjMoldSim_fill",
            "max_pressure_mpa": "log.openInjMoldSim_fill",
            "mesh_cells": "log.checkMesh",
        },
    }
    with open(output_path, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
