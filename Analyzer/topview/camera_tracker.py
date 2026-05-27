import cv2
import numpy as np

_LK_PARAMS = dict(
    winSize=(31, 31),
    maxLevel=4,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
)
_MIN_ANCHORS = 4


class CameraTracker:
    """
    카메라 이동/줌에 따른 호모그래피 갱신.

    사용자가 선택한 N개의 랜드마크 픽셀 위치를 LK 광학흐름으로 추적하고,
    매 프레임 추적된 픽셀 위치 → 필드 좌표(m) 쌍으로 H를 처음부터 재계산한다.
    → 누적 오차 없음. 앵커가 화면 밖으로 벗어나면 H를 마지막 유효값으로 유지.
    카메라가 크게 이동해 앵커가 부족해지면 'r' 키로 재보정한다.
    """

    def __init__(
        self,
        frame: np.ndarray,
        H: np.ndarray,
        src_points: list,   # pick_landmarks 가 반환한 픽셀 좌표 (원본 해상도)
        dst_points: list,   # 대응 필드 좌표 (미터)
    ):
        self.H = H.astype(np.float64).copy()
        self._anchors_px = np.float32(src_points).reshape(-1, 1, 2)
        self._anchors_m  = np.float32(dst_points).reshape(-1, 2)
        self._prev_gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # ── public ─────────────────────────────────────────────────────────

    def update(self, frame: np.ndarray) -> np.ndarray:
        """
        다음 프레임을 받아 H를 갱신한다.
        Returns: updated H (float64)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = frame.shape[:2]

        n = len(self._anchors_px)
        if n >= _MIN_ANCHORS:
            new_px, status, _ = cv2.calcOpticalFlowPyrLK(
                self._prev_gray, gray, self._anchors_px, None, **_LK_PARAMS
            )

            # 추적 성공 + 프레임 안에 있는 앵커만 유지
            ok = status.ravel() == 1
            if new_px is not None:
                ok = ok & (
                    (new_px[:, 0, 0] >= 0) & (new_px[:, 0, 0] < w) &
                    (new_px[:, 0, 1] >= 0) & (new_px[:, 0, 1] < h)
                )

            good_px = new_px[ok].reshape(-1, 1, 2)
            good_m  = self._anchors_m[ok]

            if len(good_px) >= _MIN_ANCHORS:
                # 앵커가 넉넉하면 RANSAC, 최소치면 최소자승
                method = cv2.RANSAC if len(good_px) > 6 else 0
                H_new, inliers = cv2.findHomography(
                    good_px.reshape(-1, 2), good_m, method, 5.0
                )
                if H_new is not None:
                    self.H = H_new
                    if inliers is not None:
                        keep = inliers.ravel().astype(bool)
                        self._anchors_px = good_px[keep]
                        self._anchors_m  = good_m[keep]
                    else:
                        self._anchors_px = good_px
                        self._anchors_m  = good_m
                # H_new is None → H 유지, 앵커 위치만 갱신
                else:
                    self._anchors_px = good_px
                    self._anchors_m  = good_m
            else:
                # 앵커 부족 → H 유지, 남은 앵커 보존
                if len(good_px) > 0:
                    self._anchors_px = good_px
                    self._anchors_m  = good_m

        self._prev_gray = gray
        return self.H.copy()

    def reset(self, frame: np.ndarray, H: np.ndarray,
              src_points: list, dst_points: list):
        """재보정 후 호출 ('r' 키)."""
        self.__init__(frame, H, src_points, dst_points)

    @property
    def anchor_count(self) -> int:
        return len(self._anchors_px)
