import cv2
import numpy as np


ROLE_COLORS = {
    "our_team": (210, 35, 245),
    "opponent": (245, 155, 20),
    "referee": (35, 210, 255),
    "sports ball": (245, 245, 245),
    "unknown": (190, 190, 190),
}


def _track_color(track: dict) -> tuple[int, int, int]:
    role = track.get("role", track.get("class", "unknown"))
    return ROLE_COLORS.get(role, ROLE_COLORS["unknown"])


def draw_tracks(frame, tracks: list[dict], speed_stats: dict[int, dict]):
    """Draw broadcast-style foot markers and ID tags on the original frame."""
    for t in tracks:
        x1, y1, x2, y2 = t["bbox"]
        color = _track_color(t)
        is_ball = t.get("class") == "sports ball"
        cx = int((x1 + x2) / 2)
        foot_y = int(y2)

        if is_ball:
            _draw_ball_marker(frame, cx, int((y1 + y2) / 2))
            continue

        width = max(18, int((x2 - x1) * 0.72))
        height = max(5, int(width * 0.24))
        cv2.ellipse(
            frame,
            (cx, foot_y),
            (width // 2, height),
            0,
            0,
            360,
            color,
            3,
            cv2.LINE_AA,
        )

        label = f'#{t["id"]}'
        _draw_label(frame, label, cx, foot_y + 18, color)


def draw_topview_dots(canvas, positions: list[dict], tracks: list[dict]):
    """Draw clean player/ball dots on the top-view canvas."""
    track_map = {t["id"]: t for t in tracks}

    for pos in positions:
        cx, cy = pos["cx"], pos["cy"]
        track = track_map.get(pos["id"], {})
        is_ball = track.get("class") == "sports ball"
        color = _track_color(track)
        radius = 5 if is_ball else 8

        cx = max(radius + 1, min(canvas.shape[1] - radius - 2, int(cx)))
        cy = max(radius + 1, min(canvas.shape[0] - radius - 2, int(cy)))
        cv2.circle(canvas, (cx, cy), radius + 2, (20, 30, 20), -1, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), radius, color, -1, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), radius, (8, 24, 12), 2, cv2.LINE_AA)


def _draw_label(frame, text: str, cx: int, y: int, color: tuple[int, int, int]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.58
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad_x, pad_y = 7, 4
    x1 = max(0, min(frame.shape[1] - tw - pad_x * 2, cx - tw // 2 - pad_x))
    y1 = max(0, min(frame.shape[0] - th - baseline - pad_y * 2, y))
    x2 = x1 + tw + pad_x * 2
    y2 = y1 + th + baseline + pad_y * 2

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1, cv2.LINE_AA)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (25, 25, 25), 1, cv2.LINE_AA)
    cv2.putText(
        frame,
        text,
        (x1 + pad_x, y2 - baseline - pad_y),
        font,
        scale,
        (22, 22, 24),
        thickness,
        cv2.LINE_AA,
    )


def _draw_ball_marker(frame, cx: int, cy: int) -> None:
    pts = np.array([
        (cx, cy + 14),
        (cx - 10, cy - 8),
        (cx + 10, cy - 8),
    ], dtype=np.int32)
    cv2.fillConvexPoly(frame, pts, (25, 220, 255), cv2.LINE_AA)
    cv2.polylines(frame, [pts], True, (35, 35, 35), 2, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 4, (245, 245, 245), -1, cv2.LINE_AA)
