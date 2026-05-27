import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


# ── Kalman helper ──────────────────────────────────────────────────────

def _bbox_to_z(bbox: list) -> np.ndarray:
    """[x1,y1,x2,y2] → [cx,cy,w,h]"""
    x1, y1, x2, y2 = bbox
    return np.array([(x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1], dtype=np.float32)


def _z_to_bbox(z) -> list[int]:
    """[cx,cy,w,h] → [x1,y1,x2,y2]"""
    cx, cy, w, h = float(z[0]), float(z[1]), float(z[2]), float(z[3])
    return [int(cx-w/2), int(cy-h/2), int(cx+w/2), int(cy+h/2)]


class _KalmanTrack:
    """
    SORT 방식 8D Kalman 필터 (constant-velocity).
    State : [cx, cy, w, h,  dcx, dcy, dw, dh]
    Measure: [cx, cy, w, h]
    """
    # 공유 전이 행렬 (한 번만 생성)
    _F = np.eye(8, dtype=np.float32)
    for _i in range(4):
        _F[_i, _i + 4] = 1.0

    def __init__(self, bbox: list):
        kf = cv2.KalmanFilter(8, 4)
        kf.transitionMatrix    = self._F.copy()
        kf.measurementMatrix   = np.eye(4, 8, dtype=np.float32)

        # 프로세스 노이즈 (속도 성분을 더 불확실하게)
        kf.processNoiseCov     = np.eye(8, dtype=np.float32) * 0.01
        kf.processNoiseCov[4:, 4:] *= 10.0

        # 측정 노이즈 (w, h 가 x, y 보다 불확실)
        kf.measurementNoiseCov = np.eye(4, dtype=np.float32)
        kf.measurementNoiseCov[2, 2] *= 10.0
        kf.measurementNoiseCov[3, 3] *= 10.0

        # 초기 공분산 (속도 불확실)
        kf.errorCovPost        = np.eye(8, dtype=np.float32)
        kf.errorCovPost[4:, 4:] *= 100.0

        z = _bbox_to_z(bbox)
        kf.statePost[:4, 0] = z
        self.kf = kf

    def predict(self) -> list[int]:
        """상태를 1 스텝 예측한다. 반환: 예측 bbox."""
        pred = self.kf.predict()
        return _z_to_bbox(pred[:4, 0])

    def correct(self, bbox: list) -> list[int]:
        """측정값으로 상태를 보정한다. 반환: 보정 bbox."""
        z = _bbox_to_z(bbox).reshape(4, 1)
        self.kf.correct(z)
        return _z_to_bbox(self.kf.statePost[:4, 0])

    @property
    def state_bbox(self) -> list[int]:
        return _z_to_bbox(self.kf.statePost[:4, 0])


# ── Tracker ────────────────────────────────────────────────────────────

class ByteTracker:
    """
    SORT 방식 IoU + Kalman 필터 트래커.
    detect_every > 1 일 때는 탐지 없는 프레임에서 predict_only() 를 호출해
    Kalman 상태를 계속 갱신한다. → ID 안정성 대폭 향상.
    """

    def __init__(self, max_lost: int = 60, iou_threshold: float = 0.15):
        self._next_id     = 0
        self._tracks: dict[int, dict] = {}
        self.max_lost     = max_lost
        self.iou_threshold = iou_threshold

    # ── public ──────────────────────────────────────────────────────────

    def update(self, detections: list[dict]) -> list[dict]:
        """
        탐지 결과로 트랙을 갱신한다 (탐지 프레임).
        detections: [{"bbox": [x1,y1,x2,y2], "class": str, "conf": float}, ...]
        반환:       [{"id": int, "bbox": ..., "class": str}, ...]
        """
        # 1) 모든 트랙 Kalman 예측
        for t in self._tracks.values():
            t["bbox"] = t["kf"].predict()

        if not detections:
            self._age_all()
            return self._active_tracks()

        if not self._tracks:
            for det in detections:
                self._register(det)
            return self._active_tracks()

        # 2) 예측 위치 기반 IoU 매칭
        matched_tids, matched_didxs = self._match(detections)

        # 3) 매칭된 트랙: Kalman 보정
        for tid, didx in zip(matched_tids, matched_didxs):
            new_bbox = detections[didx]["bbox"]
            corrected = self._tracks[tid]["kf"].correct(new_bbox)
            self._tracks[tid]["bbox"] = corrected
            self._tracks[tid]["lost"] = 0

        # 4) 미매칭 트랙: lost 카운터 증가
        for tid in set(self._tracks) - set(matched_tids):
            self._tracks[tid]["lost"] += 1

        self._prune()

        # 5) 미매칭 탐지: 새 트랙 등록
        for j, det in enumerate(detections):
            if j not in matched_didxs:
                self._register(det)

        return self._active_tracks()

    def predict_only(self) -> list[dict]:
        """
        탐지 없이 Kalman 상태만 1 스텝 전진한다 (비탐지 프레임).
        lost 카운터는 증가시키지 않는다.
        """
        for t in self._tracks.values():
            t["bbox"] = t["kf"].predict()
        return self._active_tracks()

    # ── internal ────────────────────────────────────────────────────────

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
            "kf":    _KalmanTrack(det["bbox"]),
        }
        self._next_id += 1

    def _age_all(self):
        for t in self._tracks.values():
            t["lost"] += 1
        self._prune()

    def _prune(self):
        dead = [tid for tid, t in self._tracks.items()
                if t["lost"] > self.max_lost]
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
