# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Running the analyzer

```powershell
# Activate virtualenv (Python 3.14)
.\venv\Scripts\Activate.ps1

# Run — must be invoked from inside Analyzer/ because imports are package-relative
cd Analyzer
python main.py
```

`main.py` expects a video at `Analyzer/data/test.mp4`. On startup it saves the first frame to `Analyzer/data/first_frame.jpg` and prompts the user to enter 4 field-corner pixel coordinates (top-left → top-right → bottom-right → bottom-left).

## Architecture

The pipeline runs frame-by-frame in `main.py`:

```
video frame
  → YoloDetector.detect()          # returns list of {bbox, class, conf}
  → ByteTracker.update()           # returns same shape + persistent "id"
  → CoordinateMapper.to_topview()  # bbox foot-point → topview (x, y)
  → cv2.imshow x2                  # original frame + top-down canvas
```

**detector/yolo_detector.py** — Thin wrapper around `ultralytics.YOLO`. Filters output to `{"person", "sports ball"}` only; everything else is discarded before leaving this layer.

**tracker/bytetrack.py** — IoU-based tracker using `scipy.optimize.linear_sum_assignment` (Hungarian algorithm). Keeps a `_tracks` dict keyed by integer ID. Tracks survive up to `max_lost=30` frames without a match before being pruned. This is a simplified ByteTrack (no low-confidence detection second pass).

**topview/homography.py → coordinate_mapper.py** — `HomographyMapper` wraps `cv2.findHomography` on the user-supplied 4-point correspondence and exposes `map_point(x, y)`. `CoordinateMapper` converts a bbox to a foot point (bottom-center) before calling the mapper — this matters because the top of a bounding box shifts with camera angle while the foot is grounded.

## Stub modules

The following files exist but are empty — they are planned extensions:

| Module | Intended purpose |
|---|---|
| `tracker/deepsort.py`, `tracker/reid.py` | Re-ID based tracker alternative |
| `stats/possession.py`, `stats/speed_calculator.py` | Per-player stats |
| `visualizer/heatmap.py`, `visualizer/overlay.py`, `visualizer/path_drawer.py` | Post-run visualizations |
| `pipeline/video_pipeline.py` | Batch/headless processing wrapper |
| `detector/classifier.py` | Team classification (jersey color) |
| `Analyzer/tests/` | All test files are currently stubs |

## Key data contract

Every layer passes detections as plain dicts — no dataclasses or NamedTuples. The shape is:

```python
# out of detector, in to tracker
{"bbox": [x1, y1, x2, y2], "class": str, "conf": float}

# out of tracker
{"id": int, "bbox": [x1, y1, x2, y2], "class": str, "conf": float}
```

Keeping this contract consistent across all future modules (stats, visualizer, pipeline) is important.
