import cv2
from collections import deque


class PathDrawer:
    """탑뷰 캔버스에 각 트랙의 최근 N 프레임 이동 경로를 그린다."""

    def __init__(self, max_len: int = 60):
        self._history: dict[int, deque] = {}
        self.max_len = max_len

    def update(self, positions: list[dict]):
        active_ids = set()
        for pos in positions:
            tid = pos["id"]
            active_ids.add(tid)
            if tid not in self._history:
                self._history[tid] = deque(maxlen=self.max_len)
            self._history[tid].append((pos["cx"], pos["cy"]))

        # 사라진 트랙 정리
        for tid in list(self._history):
            if tid not in active_ids:
                del self._history[tid]

    def draw(self, canvas):
        for tid, path in self._history.items():
            pts = list(path)
            for i in range(1, len(pts)):
                alpha = i / len(pts)
                color = (int(255 * alpha), int(200 * alpha), 50)
                cv2.line(canvas, pts[i - 1], pts[i], color, 1)
