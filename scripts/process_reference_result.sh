#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ $# -ne 2 ]]; then
    echo "usage: process_reference_result.sh SIMULATION_UUID REFERENCE_CASE" >&2
    exit 2
fi

simulation_id="$1"
reference_case="$2"

if [[ ! "$simulation_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    echo "invalid simulation UUID" >&2
    exit 3
fi
if [[ "$reference_case" != "dogbone" ]]; then
    echo "unsupported reference case" >&2
    exit 4
fi

case_dir="/home/kkwon/rms-injection-sim-cpu/tutorials/demo/dogbone"
runtime_root="${RMS_WSL_RUNTIME_ROOT:-/home/kkwon/rms-api-runtime}"
work_dir="${runtime_root}/${simulation_id}"
output_dir="${work_dir}/output"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -e "$work_dir" ]]; then
    echo "WSL work directory already exists" >&2
    exit 5
fi
if [[ ! -f "$case_dir/dogbone.foam" ]]; then
    echo "reference OpenFOAM marker is missing" >&2
    exit 6
fi

mkdir -p "$work_dir/scripts" "$output_dir"
cp -- "$script_dir/render_reference_result.py" "$work_dir/scripts/"
cp -- "$script_dir/extract_reference_kpis.py" "$work_dir/scripts/"

cd /tmp
# shellcheck disable=SC1091
set +eu
source /opt/openfoam7/etc/bashrc
set -eu

python3 "$work_dir/scripts/extract_reference_kpis.py" \
    "$case_dir" "$output_dir/source_kpis.json"

cd "$case_dir"
xvfb-run -a /opt/paraviewopenfoam56/bin/pvpython \
    "$work_dir/scripts/render_reference_result.py" \
    "$case_dir/dogbone.foam" "$output_dir"

mkdir -p "$output_dir/animations"
ffmpeg -hide_banner -loglevel error -y -framerate 10 \
    -i "$output_dir/animations/fill_frames/frame_%04d.png" \
    -c:v libx264 -pix_fmt yuv420p -movflags +faststart \
    "$output_dir/animations/fill_animation.mp4"

duration="$(ffprobe -v error -show_entries format=duration \
    -of default=noprint_wrappers=1:nokey=1 \
    "$output_dir/animations/fill_animation.mp4")"
python3 - "$duration" "$output_dir/media_probe.json" <<'PY'
import json
import sys

duration = float(sys.argv[1])
if duration <= 0:
    raise SystemExit("non-positive MP4 duration")
with open(sys.argv[2], "w") as handle:
    json.dump({"fill_animation_duration_s": duration}, handle, indent=2)
PY

echo "reference result ready: $output_dir"
