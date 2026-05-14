class SpeedCalculator:
    """
    프레임마다 각 트랙의 탑뷰 미터 좌표를 받아
    이전 프레임과의 거리로 속도(m/s)와 누적 이동거리(m)를 계산한다.
    """

    def __init__(self, fps: float):
        self.fps = fps
        self._prev_pos: dict[int, tuple[float, float]] = {}
        self._distance: dict[int, float] = {}

    def update(self, positions: list[dict]) -> dict[int, dict]:
        """
        positions: [{"id": int, "mx": float, "my": float}, ...]
        반환:      {id: {"speed": float (m/s), "distance": float (m)}}
        """
        result = {}

        for pos in positions:
            tid = pos["id"]
            mx, my = pos["mx"], pos["my"]

            if tid in self._prev_pos:
                px, py = self._prev_pos[tid]
                dist_frame = ((mx - px) ** 2 + (my - py) ** 2) ** 0.5
                self._distance[tid] = self._distance.get(tid, 0.0) + dist_frame
                speed = dist_frame * self.fps
            else:
                speed = 0.0
                self._distance[tid] = 0.0

            self._prev_pos[tid] = (mx, my)
            result[tid] = {
                "speed":    round(speed, 2),
                "distance": round(self._distance[tid], 2),
            }

        # 사라진 트랙 정리
        active_ids = {p["id"] for p in positions}
        for tid in list(self._prev_pos):
            if tid not in active_ids:
                del self._prev_pos[tid]

        return result
