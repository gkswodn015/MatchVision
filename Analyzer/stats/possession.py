class PossessionTracker:
    """
    공(sports ball)과 가장 가까운 선수에게 점유권을 부여한다.
    점유 판정 거리(미터) 이내에 선수가 없으면 중립 처리.
    """

    POSSESSION_RADIUS = 3.0  # 미터

    def __init__(self):
        self._frames: dict[int, int] = {}   # {track_id: 점유 프레임 수}
        self._total = 0

    def update(self, tracks: list[dict], positions: list[dict]) -> dict[int, float]:
        """
        tracks:    [{"id": int, "class": str, ...}]
        positions: [{"id": int, "mx": float, "my": float}]
        반환:      {track_id: 점유율 (0.0~1.0)}
        """
        pos_map = {p["id"]: (p["mx"], p["my"]) for p in positions}

        ball_pos = None
        for t in tracks:
            if t["class"] == "sports ball" and t["id"] in pos_map:
                ball_pos = pos_map[t["id"]]
                break

        if ball_pos is None:
            return self._ratios()

        bx, by = ball_pos
        closest_id, closest_dist = None, float("inf")

        for t in tracks:
            if t["class"] != "person" or t["id"] not in pos_map:
                continue
            px, py = pos_map[t["id"]]
            dist = ((px - bx) ** 2 + (py - by) ** 2) ** 0.5
            if dist < closest_dist:
                closest_dist = dist
                closest_id = t["id"]

        if closest_id is not None and closest_dist <= self.POSSESSION_RADIUS:
            self._frames[closest_id] = self._frames.get(closest_id, 0) + 1
            self._total += 1

        return self._ratios()

    def _ratios(self) -> dict[int, float]:
        if self._total == 0:
            return {}
        return {tid: round(f / self._total, 3) for tid, f in self._frames.items()}
