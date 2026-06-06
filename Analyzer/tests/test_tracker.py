import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tracker.bytetrack import ByteTracker


def _det(x1, y1, x2, y2, appearance=None, role="our_team"):
    return {
        "bbox": [x1, y1, x2, y2],
        "class": "person",
        "role": role,
        "conf": 0.9,
        "appearance": appearance,
    }


def test_id_survives_low_iou_motion():
    tracker = ByteTracker()
    first = tracker.update([_det(100, 100, 140, 200)])
    first_id = first[0]["id"]

    second = tracker.update([_det(128, 104, 168, 204)])

    assert second[0]["id"] == first_id


def test_id_survives_short_detection_gap():
    tracker = ByteTracker()
    first = tracker.update([_det(100, 100, 140, 200)])
    first_id = first[0]["id"]

    tracker.update([])
    tracker.update([])
    after_gap = tracker.update([_det(112, 102, 152, 202)])

    assert after_gap[0]["id"] == first_id


def test_appearance_breaks_nearby_tie():
    red = np.array([1.0, 0.0, 0.8, 0.8], dtype=np.float32)
    blue = np.array([-1.0, 0.0, 0.8, 0.8], dtype=np.float32)

    tracker = ByteTracker()
    tracks = tracker.update([
        _det(100, 100, 140, 200, red, "our_team"),
        _det(180, 100, 220, 200, blue, "opponent"),
    ])
    ids = {track["role"]: track["id"] for track in tracks}

    tracks = tracker.update([
        _det(178, 100, 218, 200, blue, "opponent"),
        _det(104, 100, 144, 200, red, "our_team"),
    ])
    ids_after = {track["role"]: track["id"] for track in tracks}

    assert ids_after["our_team"] == ids["our_team"]
    assert ids_after["opponent"] == ids["opponent"]


def test_ball_does_not_reuse_person_id():
    tracker = ByteTracker()
    person_id = tracker.update([_det(100, 100, 140, 200)])[0]["id"]

    tracks = tracker.update([
        {
            "bbox": [105, 105, 120, 120],
            "class": "sports ball",
            "role": "sports ball",
            "conf": 0.9,
        }
    ])

    assert all(track["id"] != person_id or track["class"] == "person" for track in tracks)


def test_role_locks_after_consistent_votes():
    tracker = ByteTracker(lock_min_hits=4, lock_ratio=0.75)

    tracks = []
    for _ in range(4):
        tracks = tracker.update([_det(100, 100, 140, 200, role="our_team")])

    assert tracks[0]["locked_role"] == "our_team"
    assert tracks[0]["role"] == "our_team"

    tracks = tracker.update([_det(101, 100, 141, 200, role="opponent")])

    assert tracks[0]["id"] == 1
    assert tracks[0]["locked_role"] == "our_team"
    assert tracks[0]["role"] == "our_team"
