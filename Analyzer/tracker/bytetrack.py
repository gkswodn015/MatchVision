import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from collections import Counter, deque


def _bbox_to_z(bbox: list) -> np.ndarray:
    """Convert [x1, y1, x2, y2] to [cx, cy, w, h]."""
    x1, y1, x2, y2 = bbox
    return np.array([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1], dtype=np.float32)


def _z_to_bbox(z) -> list[int]:
    """Convert [cx, cy, w, h] to [x1, y1, x2, y2]."""
    cx, cy, w, h = float(z[0]), float(z[1]), float(z[2]), float(z[3])
    w = max(2.0, w)
    h = max(2.0, h)
    return [int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2)]


class _KalmanTrack:
    """Constant-velocity Kalman filter for bbox center, size, and velocity."""

    _F = np.eye(8, dtype=np.float32)
    for _i in range(4):
        _F[_i, _i + 4] = 1.0

    def __init__(self, bbox: list):
        kf = cv2.KalmanFilter(8, 4)
        kf.transitionMatrix = self._F.copy()
        kf.measurementMatrix = np.eye(4, 8, dtype=np.float32)
        kf.processNoiseCov = np.eye(8, dtype=np.float32) * 0.02
        kf.processNoiseCov[4:, 4:] *= 14.0
        kf.measurementNoiseCov = np.eye(4, dtype=np.float32)
        kf.measurementNoiseCov[2, 2] *= 8.0
        kf.measurementNoiseCov[3, 3] *= 8.0
        kf.errorCovPost = np.eye(8, dtype=np.float32)
        kf.errorCovPost[4:, 4:] *= 100.0

        z = _bbox_to_z(bbox)
        state = np.zeros((8, 1), dtype=np.float32)
        state[:4, 0] = z
        kf.statePost = state.copy()
        kf.statePre = state.copy()
        self.kf = kf

    def predict(self) -> list[int]:
        pred = self.kf.predict()
        return _z_to_bbox(pred[:4, 0])

    def correct(self, bbox: list) -> list[int]:
        z = _bbox_to_z(bbox).reshape(4, 1)
        self.kf.correct(z)
        return _z_to_bbox(self.kf.statePost[:4, 0])


class ByteTracker:
    """
    SORT-style tracker tuned for football broadcast footage.

    A pure IoU match is brittle because player boxes jitter and briefly disappear.
    This tracker gates by predicted center distance, then scores candidates with
    IoU, center proximity, bbox size similarity, and optional torso-color appearance.
    """

    def __init__(
        self,
        max_lost: int = 90,
        visible_lost: int = 18,
        match_threshold: float = 0.34,
        min_iou: float = 0.02,
    ):
        self._next_id = 1
        self._tracks: dict[int, dict] = {}
        self.max_lost = max_lost
        self.visible_lost = visible_lost
        self.match_threshold = match_threshold
        self.min_iou = min_iou

    def update(self, detections: list[dict]) -> list[dict]:
        for track in self._tracks.values():
            track["bbox"] = track["kf"].predict()

        if not detections:
            self._age_all()
            return self._active_tracks()

        if not self._tracks:
            for det in detections:
                self._register(det)
            return self._active_tracks()

        matched_tids, matched_didxs = self._match(detections)
        matched_tid_set = set(matched_tids)
        matched_det_set = set(matched_didxs)

        for tid, didx in zip(matched_tids, matched_didxs):
            self._update_track(tid, detections[didx])

        for tid in set(self._tracks) - matched_tid_set:
            self._tracks[tid]["lost"] += 1

        self._prune()

        for didx, det in enumerate(detections):
            if didx not in matched_det_set:
                self._register(det)

        return self._active_tracks()

    def predict_only(self) -> list[dict]:
        for track in self._tracks.values():
            track["bbox"] = track["kf"].predict()
        return self._active_tracks()

    def _match(self, detections: list[dict]) -> tuple[list[int], list[int]]:
        track_ids = list(self._tracks.keys())
        scores = np.full((len(track_ids), len(detections)), -1.0, dtype=np.float32)

        for row, tid in enumerate(track_ids):
            track = self._tracks[tid]
            for col, det in enumerate(detections):
                score = self._score(track, det)
                if score is not None:
                    scores[row, col] = score

        row_ind, col_ind = linear_sum_assignment(-scores)

        matched_tids, matched_didxs = [], []
        for row, col in zip(row_ind, col_ind):
            score = float(scores[row, col])
            if score >= self.match_threshold:
                matched_tids.append(track_ids[row])
                matched_didxs.append(col)

        return matched_tids, matched_didxs

    def _score(self, track: dict, det: dict) -> float | None:
        if not self._classes_compatible(track.get("class"), det.get("class")):
            return None

        tb = track["bbox"]
        db = det["bbox"]
        iou = self._iou(tb, db)
        dist = self._center_distance(tb, db)
        diag = max(self._diag(tb), self._diag(db), 1.0)
        lost = min(track.get("lost", 0), 12)

        # Broadcast frames are high-resolution; use both box-relative and absolute gates.
        center_gate = max(55.0, diag * (1.25 + 0.18 * lost))
        if iou < self.min_iou and dist > center_gate:
            return None

        distance_score = max(0.0, 1.0 - dist / center_gate)
        size_score = self._size_similarity(tb, db)
        appearance_score = self._appearance_similarity(track.get("appearance"), det.get("appearance"))

        if appearance_score is None:
            score = 0.46 * iou + 0.42 * distance_score + 0.12 * size_score
        else:
            score = (
                0.34 * iou
                + 0.34 * distance_score
                + 0.10 * size_score
                + 0.22 * appearance_score
            )

        track_role = track.get("role")
        det_role = det.get("role", det.get("class"))
        if (
            track_role
            and det_role
            and track_role != "unknown"
            and det_role != "unknown"
            and track_role != det_role
        ):
            score -= 0.08

        return score

    def _register(self, det: dict):
        self._tracks[self._next_id] = {
            "bbox": det["bbox"],
            "class": det["class"],
            "role": det.get("role", det["class"]),
            "role_votes": deque([det.get("role", det["class"])], maxlen=18),
            "appearance": self._copy_appearance(det.get("appearance")),
            "lost": 0,
            "hits": 1,
            "kf": _KalmanTrack(det["bbox"]),
        }
        self._next_id += 1

    def _update_track(self, tid: int, det: dict):
        track = self._tracks[tid]
        track["bbox"] = track["kf"].correct(det["bbox"])
        track["class"] = det["class"]
        det_role = det.get("role", det["class"])
        track["role_votes"].append(det_role)
        track["role"] = self._stable_role(track)
        track["lost"] = 0
        track["hits"] += 1

        det_app = det.get("appearance")
        if det_app is not None:
            det_app = np.float32(det_app)
            if track.get("appearance") is None:
                track["appearance"] = det_app.copy()
            else:
                alpha = 0.08
                track["appearance"] = track["appearance"] * (1.0 - alpha) + det_app * alpha

    def _age_all(self):
        for track in self._tracks.values():
            track["lost"] += 1
        self._prune()

    def _prune(self):
        dead = [tid for tid, track in self._tracks.items() if track["lost"] > self.max_lost]
        for tid in dead:
            del self._tracks[tid]

    def _active_tracks(self) -> list[dict]:
        return [
            {
                "id": tid,
                "bbox": track["bbox"],
                "class": track["class"],
                "role": track.get("role", track["class"]),
                "role_votes": dict(Counter(track.get("role_votes", []))),
                "lost": track.get("lost", 0),
                "hits": track.get("hits", 0),
                "predicted": track.get("lost", 0) > 0,
            }
            for tid, track in self._tracks.items()
            if track["lost"] <= self.visible_lost
        ]

    @staticmethod
    def _stable_role(track: dict) -> str:
        votes = [
            role for role in track.get("role_votes", [])
            if role and role != "unknown"
        ]
        if not votes:
            return track.get("role", track.get("class", "unknown"))
        return Counter(votes).most_common(1)[0][0]

    @staticmethod
    def _copy_appearance(value):
        if value is None:
            return None
        return np.float32(value).copy()

    @staticmethod
    def _classes_compatible(a: str | None, b: str | None) -> bool:
        return a == b

    @staticmethod
    def _appearance_similarity(a, b) -> float | None:
        if a is None or b is None:
            return None
        dist = float(np.linalg.norm(np.float32(a) - np.float32(b)))
        return max(0.0, 1.0 - dist / 1.3)

    @staticmethod
    def _center_distance(a: list, b: list) -> float:
        acx, acy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
        bcx, bcy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        return float(((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5)

    @staticmethod
    def _diag(bbox: list) -> float:
        return float(((bbox[2] - bbox[0]) ** 2 + (bbox[3] - bbox[1]) ** 2) ** 0.5)

    @staticmethod
    def _size_similarity(a: list, b: list) -> float:
        area_a = max(1, (a[2] - a[0]) * (a[3] - a[1]))
        area_b = max(1, (b[2] - b[0]) * (b[3] - b[1]))
        return min(area_a, area_b) / max(area_a, area_b)

    @staticmethod
    def _iou(a: list, b: list) -> float:
        ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
        ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter == 0:
            return 0.0
        area_a = max(1, (a[2] - a[0]) * (a[3] - a[1]))
        area_b = max(1, (b[2] - b[0]) * (b[3] - b[1]))
        return inter / (area_a + area_b - inter)
