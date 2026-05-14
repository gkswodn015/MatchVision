import cv2


def draw_tracks(frame, tracks: list[dict], speed_stats: dict[int, dict]):
    """원본 프레임에 bbox, ID, 속도를 그린다."""
    for t in tracks:
        x1, y1, x2, y2 = t["bbox"]
        color = (0, 200, 255) if t["class"] == "sports ball" else (0, 255, 0)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        stat = speed_stats.get(t["id"], {})
        speed = stat.get("speed", 0.0)
        label = f'ID:{t["id"]}  {speed:.1f}m/s'
        cv2.putText(frame, label, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def draw_topview_dots(canvas, positions: list[dict], tracks: list[dict]):
    """탑뷰 캔버스에 선수/공 위치를 점으로 그린다."""
    class_map = {t["id"]: t["class"] for t in tracks}

    for pos in positions:
        cx, cy = pos["cx"], pos["cy"]
        is_ball = class_map.get(pos["id"]) == "sports ball"
        color = (0, 200, 255) if is_ball else (255, 255, 0)
        radius = 5 if is_ball else 7

        cv2.circle(canvas, (cx, cy), radius, color, -1)
        cv2.putText(canvas, str(pos["id"]), (cx + 8, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
