import cv2
import numpy as np
from topview.field_landmarks import FIELD_W, FIELD_H

# 한글 윈도우 이름은 Windows OpenCV에서 namedWindow/imshow 불일치를 유발함
WINDOW = "MatchVision - Corner Selection"

_ZOOM_SIZE   = 140
_ZOOM_FACTOR = 5

# 클릭 순서 고정: 좌상 → 우상 → 우하 → 좌하
_CORNER_NAMES: list[str] = ["좌상 코너", "우상 코너", "우하 코너", "좌하 코너"]
_CORNER_COORDS: list[tuple[float, float]] = [
    (0.0,    0.0),
    (FIELD_W, 0.0),
    (FIELD_W, FIELD_H),
    (0.0,    FIELD_H),
]


def pick_landmarks(frame: np.ndarray) -> tuple[list[list[int]], list[list[float]]]:
    """
    첫 프레임에서 경기장 4 코너를 클릭 → 호모그래피 대응점 반환.
    4 코너가 항상 보이는 영상을 전제로 하며, 필드 전체가 변환 정의역이 된다.
    반환: (픽셀 src_points 4개, 미터 dst_points 4개)
    """
    print("\n=== 경기장 4 코너 선택 ===")
    print("  좌상 → 우상 → 우하 → 좌하 순서로 클릭하세요.")
    print("  • Backspace: 마지막 점 취소\n")

    h, w = frame.shape[:2]
    scale = min(1280 / w, 720 / h, 1.0)
    base = cv2.resize(frame, (int(w * scale), int(h * scale)))

    pts_display = _click_corners(base)

    src_points = [[int(x / scale), int(y / scale)] for x, y in pts_display]
    dst_points = [list(c) for c in _CORNER_COORDS]
    return src_points, dst_points


def _click_corners(base: np.ndarray) -> list[list[int]]:
    pts: list[list[int]] = []
    canvas = [_rebuild(base, pts)]

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < 4:
            pts.append([x, y])
            canvas[0] = _rebuild(base, pts)
        if event in (cv2.EVENT_LBUTTONDOWN, cv2.EVENT_MOUSEMOVE):
            vis = canvas[0].copy()
            _draw_zoom_inset(vis, x, y)
            cv2.imshow(WINDOW, vis)

    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW, on_mouse)
    cv2.imshow(WINDOW, canvas[0])

    while len(pts) < 4:
        key = cv2.waitKey(30) & 0xFF
        if key == ord("q"):
            raise RuntimeError("사용자가 취소했습니다.")
        if key in (8, 127) and pts:  # Backspace / Delete
            pts.pop()
            canvas[0] = _rebuild(base, pts)
            cv2.imshow(WINDOW, canvas[0])

    cv2.destroyWindow(WINDOW)
    return pts


def _rebuild(base: np.ndarray, pts: list[list[int]]) -> np.ndarray:
    c = base.copy()
    for i, (px, py) in enumerate(pts):
        cv2.circle(c, (px, py), 6, (0, 255, 255), -1)
        cv2.putText(c, _CORNER_NAMES[i], (px + 8, py - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    _draw_guide(c, len(pts))
    return c


def _draw_guide(frame: np.ndarray, done: int):
    bar_w = min(560, frame.shape[1])
    overlay = frame[:40, :bar_w].copy()
    cv2.rectangle(frame, (0, 0), (bar_w, 40), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.35, frame[:40, :bar_w], 0.65, 0, frame[:40, :bar_w])

    if done < 4:
        text = f"클릭 ({done}/4): {_CORNER_NAMES[done]}  |  Backspace: 취소"
    else:
        text = "4개 완료 — 닫는 중..."

    cv2.putText(frame, text, (8, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def _draw_zoom_inset(frame: np.ndarray, cx: int, cy: int):
    fh, fw = frame.shape[:2]
    half = _ZOOM_SIZE // (2 * _ZOOM_FACTOR)

    x1, y1 = max(0, cx - half), max(0, cy - half)
    x2, y2 = min(fw, cx + half), min(fh, cy + half)
    if x2 <= x1 or y2 <= y1:
        return

    zoomed = cv2.resize(frame[y1:y2, x1:x2], (_ZOOM_SIZE, _ZOOM_SIZE),
                        interpolation=cv2.INTER_LINEAR)
    mid = _ZOOM_SIZE // 2
    cv2.line(zoomed, (mid, 0), (mid, _ZOOM_SIZE - 1), (0, 255, 0), 1)
    cv2.line(zoomed, (0, mid), (_ZOOM_SIZE - 1, mid), (0, 255, 0), 1)
    cv2.rectangle(zoomed, (0, 0), (_ZOOM_SIZE - 1, _ZOOM_SIZE - 1), (0, 255, 0), 2)

    px = fw - _ZOOM_SIZE - 6
    py = 46
    if py + _ZOOM_SIZE <= fh and px >= 0:
        frame[py:py + _ZOOM_SIZE, px:px + _ZOOM_SIZE] = zoomed
