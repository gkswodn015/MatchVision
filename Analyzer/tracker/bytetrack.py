import numpy as np
from scipy.optimize import linear_sum_assignment


class ByteTracker:
    """
    IoU 기반 트래커.
    매 프레임 탐지 결과를 받아 기존 트랙과 매칭하고 ID를 유지한다.
    """

    def __init__(self, max_lost: int = 30, iou_threshold: float = 0.3):
        self._next_id = 0
        self._tracks: dict[int, dict] = {}
        self.max_lost = max_lost
        self.iou_threshold = iou_threshold

    def update(self, detections: list[dict]) -> list[dict]:
        """
        detections: [{"bbox": [x1,y1,x2,y2], "class": str, "conf": float}, ...]
        반환:       [{"id": int, "bbox": ..., "class": str}, ...]
        """
        if not detections:
            self._age_all()
            return []

        if not self._tracks:
            for det in detections:
                self._register(det)
            return self._active_tracks()

        matched_tids, matched_didxs = self._match(detections)

        for tid, didx in zip(matched_tids, matched_didxs):
            self._tracks[tid]["bbox"] = detections[didx]["bbox"]
            self._tracks[tid]["lost"] = 0

        for tid in set(self._tracks) - set(matched_tids):
            self._tracks[tid]["lost"] += 1

        self._prune()

        for j, det in enumerate(detections):
            if j not in matched_didxs:
                self._register(det)

        return self._active_tracks()

    def _match(self, detections: list[dict]) -> tuple[list, list]:
        track_ids    = list(self._tracks.keys())
        track_bboxes = [self._tracks[t]["bbox"] for t in track_ids]
        det_bboxes   = [d["bbox"] for d in detections]

        iou_matrix = np.array([
            [self._iou(tb, db) for db in det_bboxes]
            for tb in track_bboxes
        ])

        row_ind, col_ind = linear_sum_assignment(-iou_matrix)

        matched_tids, matched_didxs = [], []
        for r, c in zip(row_ind, col_ind):
            if iou_matrix[r, c] >= self.iou_threshold:
                matched_tids.append(track_ids[r])
                matched_didxs.append(c)

        return matched_tids, matched_didxs

    def _register(self, det: dict):
        self._tracks[self._next_id] = {
            "bbox":  det["bbox"],
            "class": det["class"],
            "lost":  0,
        }
        self._next_id += 1

    def _age_all(self):
        for t in self._tracks.values():
            t["lost"] += 1
        self._prune()

    def _prune(self):
        dead = [tid for tid, t in self._tracks.items() if t["lost"] > self.max_lost]
        for tid in dead:
            del self._tracks[tid]

    def _active_tracks(self) -> list[dict]:
        return [
            {"id": tid, "bbox": t["bbox"], "class": t["class"]}
            for tid, t in self._tracks.items()
            if t["lost"] == 0
        ]

    @staticmethod
    def _iou(a: list, b: list) -> float:
        ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
        ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter == 0:
            return 0.0
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        return inter / (area_a + area_b - inter)
