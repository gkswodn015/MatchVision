import cv2


ROLE_COLORS = {
    "our_team": (255, 80, 40),
    "opponent": (40, 220, 255),
    "referee": (220, 40, 220),
    "sports ball": (0, 200, 255),
    "unknown": (200, 200, 200),
}


def _track_color(track: dict) -> tuple[int, int, int]:
    role = track.get("role", track.get("class", "unknown"))
    return ROLE_COLORS.get(role, ROLE_COLORS["unknown"])


def draw_tracks(frame, tracks: list[dict], speed_stats: dict[int, dict]):
    """Draw bbox, ID, role, and speed on the original frame."""
    for t in tracks:
        x1, y1, x2, y2 = t["bbox"]
        color = _track_color(t)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        stat = speed_stats.get(t["id"], {})
        speed = stat.get("speed", 0.0)
        role = t.get("role", t["class"])
        label = f'ID:{t["id"]} {role} {speed:.1f}m/s'
        cv2.putText(frame, label, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def draw_topview_dots(canvas, positions: list[dict], tracks: list[dict]):
    """Draw player/ball dots on the top-view canvas."""
    track_map = {t["id"]: t for t in tracks}

    for pos in positions:
        cx, cy = pos["cx"], pos["cy"]
        track = track_map.get(pos["id"], {})
        is_ball = track.get("class") == "sports ball"
        color = _track_color(track)
        radius = 5 if is_ball else 7

        cv2.circle(canvas, (cx, cy), radius, color, -1)
        cv2.putText(canvas, str(pos["id"]), (cx + 8, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
