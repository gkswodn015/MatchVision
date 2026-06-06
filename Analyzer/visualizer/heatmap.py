import cv2
import numpy as np
from topview.coordinate_mapper import CANVAS_W, CANVAS_H


class Heatmap:
    """
    탑뷰 좌표를 누적해 히트맵을 생성한다.
    특정 선수(track_id)만 추적하거나, 전체 선수를 누적할 수 있다.
    """

    def __init__(self):
        self._accumulator = np.zeros((CANVAS_H, CANVAS_W), dtype=np.float32)

    def update(self, positions: list[dict], track_ids: set[int] | None = None):
        """
        track_ids: None 이면 전체 선수, 지정하면 해당 ID만 누적
        """
        for pos in positions:
            if track_ids is not None and pos["id"] not in track_ids:
                continue
            cx, cy = pos["cx"], pos["cy"]
            if 0 <= cx < CANVAS_W and 0 <= cy < CANVAS_H:
                self._accumulator[cy, cx] += 1.0

    def render(self, alpha: float = 0.5) -> np.ndarray:
        """히트맵 이미지를 반환한다 (BGR, CANVAS_H x CANVAS_W)."""
        norm = cv2.normalize(self._accumulator, None, 0, 255, cv2.NORM_MINMAX)
        colored = cv2.applyColorMap(norm.astype(np.uint8), cv2.COLORMAP_JET)
        return colored

    def overlay_on(self, canvas: np.ndarray, alpha: float = 0.5) -> np.ndarray:
        """히트맵을 탑뷰 캔버스 위에 반투명하게 합성해 반환한다."""
        heatmap = self.render()
        return cv2.addWeighted(canvas, 1 - alpha, heatmap, alpha, 0)
