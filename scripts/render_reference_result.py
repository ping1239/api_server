# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import math
import os
import sys

from paraview.simple import *


if len(sys.argv) != 3:
    print("Usage: pvpython render_reference_result.py CASE.foam OUTPUT_DIR")
    sys.exit(1)

case_file = os.path.abspath(sys.argv[1])
out_root = os.path.abspath(sys.argv[2])
final_dir = os.path.join(out_root, "final")
frame_dir = os.path.join(out_root, "animations", "fill_frames")
for directory in (final_dir, frame_dir):
    if not os.path.exists(directory):
        os.makedirs(directory)

reader = OpenFOAMReader(FileName=case_file)
reader.UpdatePipelineInformation()
if hasattr(reader, "MeshRegions"):
    reader.MeshRegions = ["internalMesh"]
if hasattr(reader, "CellArrays"):
    reader.CellArrays = ["alpha.poly", "p", "T", "shrRate"]

times = sorted(list(reader.TimestepValues))
if not times:
    print("ERROR: no physical timesteps found")
    sys.exit(2)

reader.UpdatePipeline(times[-1])
threshold = Threshold(Input=reader)
threshold.Scalars = ["CELLS", "alpha.poly"]
threshold.ThresholdRange = [0.5, 1.0]
threshold.UpdatePipeline(times[-1])
c2p = CellDatatoPointData(Input=threshold)
c2p.UpdatePipeline(times[-1])

pressure = Calculator(Input=c2p)
pressure.ResultArrayName = "pressure_MPa"
pressure.Function = "p/1000000.0"
temperature = Calculator(Input=c2p)
temperature.ResultArrayName = "temperature_C"
temperature.Function = "T-273.15"


def update_all(time_value):
    reader.UpdatePipeline(time_value)
    threshold.UpdatePipeline(time_value)
    c2p.UpdatePipeline(time_value)
    pressure.UpdatePipeline(time_value)
    temperature.UpdatePipeline(time_value)


def point_range(source, array_name):
    info = source.GetDataInformation().GetPointDataInformation()
    array_info = info.GetArrayInformation(array_name)
    if array_info is None:
        raise RuntimeError("required point array not found: " + array_name)
    return array_info.GetComponentRange(0)


ranges = {
    "pressure_MPa": [None, None],
    "temperature_C": [None, None],
    "shrRate": [None, None],
}
for index, time_value in enumerate(times):
    update_all(time_value)
    current = {
        "pressure_MPa": point_range(pressure, "pressure_MPa"),
        "temperature_C": point_range(temperature, "temperature_C"),
        "shrRate": point_range(c2p, "shrRate"),
    }
    for name, pair in current.items():
        if ranges[name][0] is None or pair[0] < ranges[name][0]:
            ranges[name][0] = pair[0]
        if ranges[name][1] is None or pair[1] > ranges[name][1]:
            ranges[name][1] = pair[1]
    print("range scan {}/{} time={}".format(index + 1, len(times), time_value))

pressure_hi = max(1.0, float(math.ceil(ranges["pressure_MPa"][1])))
temperature_lo = math.floor(ranges["temperature_C"][0] / 5.0) * 5.0
temperature_hi = math.ceil(ranges["temperature_C"][1] / 5.0) * 5.0
shear_hi = max(1.0, math.ceil(ranges["shrRate"][1] / 500.0) * 500.0)

field_metrics = {
    "max_pressure_mpa": ranges["pressure_MPa"][1],
    "min_temperature_c": ranges["temperature_C"][0],
    "max_temperature_c": ranges["temperature_C"][1],
    "max_shear_rate_1_s": ranges["shrRate"][1],
    "physical_time_count": len(times),
    "first_time_s": times[0],
    "final_time_s": times[-1],
}
with open(os.path.join(out_root, "field_metrics.json"), "w") as handle:
    json.dump(field_metrics, handle, indent=2, sort_keys=True)

update_all(times[-1])
bounds = c2p.GetDataInformation().GetBounds()
xmin, xmax, ymin, ymax, zmin, zmax = bounds
cx = 0.5 * (xmin + xmax)
cy = 0.5 * (ymin + ymax)
cz = 0.5 * (zmin + zmax)
span = max(xmax - xmin, ymax - ymin)

view = GetActiveViewOrCreate("RenderView")
view.ViewSize = [1600, 900]
view.Background = [0.12, 0.12, 0.12]
view.CameraFocalPoint = [cx, cy, cz]
view.CameraPosition = [cx, cy + 1.50 * span, cz + 2.60 * span]
view.CameraViewUp = [0.0, 0.866, -0.5]
view.CameraParallelProjection = 0


def configure_display(source, array_name, low, high, title, unit):
    display = Show(source, view)
    display.Representation = "Surface"
    ColorBy(display, ("POINTS", array_name))
    lookup = GetColorTransferFunction(array_name)
    lookup.RescaleTransferFunction(low, high)
    opacity = GetOpacityTransferFunction(array_name)
    opacity.RescaleTransferFunction(low, high)
    display.SetScalarBarVisibility(view, True)
    scalar_bar = GetScalarBar(lookup, view)
    scalar_bar.Title = title
    scalar_bar.ComponentTitle = unit
    scalar_bar.RangeLabelFormat = "%-#6.4g"
    return display


def render_final(source, array_name, low, high, title, unit, filename):
    display = configure_display(source, array_name, low, high, title, unit)
    update_all(times[-1])
    view.ViewTime = times[-1]
    Render()
    SaveScreenshot(os.path.join(final_dir, filename), view, ImageResolution=[1600, 900])
    display.SetScalarBarVisibility(view, False)
    Hide(source, view)


fill_display = configure_display(c2p, "alpha.poly", 0.0, 1.0, "Fill fraction", "[-]")
update_all(times[-1])
view.ViewTime = times[-1]
Render()
SaveScreenshot(os.path.join(final_dir, "fill_final.png"), view, ImageResolution=[1600, 900])
for index, time_value in enumerate(times):
    update_all(time_value)
    view.ViewTime = time_value
    Render()
    SaveScreenshot(
        os.path.join(frame_dir, "frame_{:04d}.png".format(index)),
        view,
        ImageResolution=[1600, 900],
    )
    print("fill frame {}/{} time={}".format(index + 1, len(times), time_value))
fill_display.SetScalarBarVisibility(view, False)
Hide(c2p, view)

render_final(
    pressure,
    "pressure_MPa",
    0.0,
    pressure_hi,
    "Pressure",
    "[MPa]",
    "pressure_final.png",
)
render_final(
    temperature,
    "temperature_C",
    temperature_lo,
    temperature_hi,
    "Temperature",
    "[degC]",
    "temperature_final.png",
)
render_final(
    c2p,
    "shrRate",
    0.0,
    shear_hi,
    "Shear rate",
    "[1/s]",
    "shear_rate_final.png",
)

print("reference rendering complete")
