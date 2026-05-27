import math
import cv2
import numpy as np

THUMB_W  = 260
THUMB_H  = 146
PAD      = 8
LABEL_H  = 22
CELL_W   = THUMB_W + PAD
CELL_H   = THUMB_H + LABEL_H + PAD
COLS     = 4
ROWS_VIS = 3
BOTTOM_H = 44
WIN_W    = COLS * CELL_W + PAD
WIN_H    = ROWS_VIS * CELL_H + PAD + BOTTOM_H

_WIN  = "Keyframe Selector"   # ASCII name — Korean title breaks setMouseCallback on Windows
_BG   = (30, 30, 30)
_SEL  = (0, 200, 80)
_UNSEL = (60, 60, 60)


def extract_keyframes(
    video_path: str,
    interval_sec: float = 5.0,
    max_frames: int = 50,
) -> list[tuple[int, np.ndarray]]:
    """Extract frames at regular intervals. Returns [(frame_idx, frame), ...]."""
    cap   = cv2.VideoCapture(video_path)
    fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    step = max(1, int(fps * interval_sec))
    if total // max(step, 1) > max_frames:
        step = max(1, total // max_frames)

    out: list[tuple[int, np.ndarray]] = []
    idx = 0
    while idx < total:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            out.append((idx, frame.copy()))
        idx += step

    cap.release()
    return out


def select_keyframes(
    keyframes: list[tuple[int, np.ndarray]],
    fps: float = 30.0,
) -> list[tuple[int, np.ndarray]]:
    """
    Grid UI for selecting frames to calibrate on.
    Controls: left-click to toggle, W/S or mouse wheel to scroll, Enter to confirm.
    Returns selected subset in frame-index order.
    """
    if not keyframes:
        return []

    thumbs: list[tuple[int, np.ndarray, str]] = []
    for frame_idx, frame in keyframes:
        th  = cv2.resize(frame, (THUMB_W, THUMB_H))
        m, s = divmod(int(frame_idx / fps), 60)
        thumbs.append((frame_idx, th, f"{m:02d}:{s:02d}  f{frame_idx}"))

    total_rows = math.ceil(len(thumbs) / COLS)
    max_scroll = max(0, total_rows - ROWS_VIS)
    scroll_row = 0
    selected: set[int] = set()
    redraw = [True]

    def on_mouse(event, x, y, flags, _):
        nonlocal scroll_row
        if event == cv2.EVENT_LBUTTONDOWN:
            gx, gy = x - PAD, y - PAD
            if gx < 0 or gy < 0 or gy >= ROWS_VIS * CELL_H:
                return
            col = gx // CELL_W
            rv  = gy  // CELL_H
            if col >= COLS:
                return
            i = (scroll_row + rv) * COLS + col
            if 0 <= i < len(thumbs):
                selected.discard(i) if i in selected else selected.add(i)
                redraw[0] = True
        elif event == cv2.EVENT_MOUSEWHEEL:
            # flags > 0 = wheel up → show earlier rows
            delta = -1 if flags > 0 else 1
            scroll_row = max(0, min(max_scroll, scroll_row + delta))
            redraw[0] = True

    cv2.namedWindow(_WIN, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(_WIN, on_mouse)

    while True:
        if redraw[0]:
            cv2.imshow(_WIN, _render(thumbs, selected, scroll_row))
            redraw[0] = False

        key = cv2.waitKey(30) & 0xFF
        if key in (ord('w'), ord('W')):
            scroll_row = max(0, scroll_row - 1)
            redraw[0] = True
        elif key in (ord('s'), ord('S')):
            scroll_row = min(max_scroll, scroll_row + 1)
            redraw[0] = True
        elif key in (13, 10) and selected:   # Enter — need at least one frame
            break
        elif key == 27:                       # ESC → fall back to first frame
            selected.add(0)
            break

    cv2.destroyWindow(_WIN)
    return [keyframes[i] for i in sorted(selected)]


def _render(
    thumbs: list[tuple[int, np.ndarray, str]],
    selected: set[int],
    scroll_row: int,
) -> np.ndarray:
    canvas = np.full((WIN_H, WIN_W, 3), _BG, dtype=np.uint8)

    for rv in range(ROWS_VIS):
        row = scroll_row + rv
        for col in range(COLS):
            i = row * COLS + col
            if i >= len(thumbs):
                break
            _, th, lbl = thumbs[i]
            cx = PAD + col * CELL_W
            cy = PAD + rv  * CELL_H

            canvas[cy:cy + THUMB_H, cx:cx + THUMB_W] = th

            bc, bt = (_SEL, 3) if i in selected else (_UNSEL, 1)
            cv2.rectangle(canvas, (cx - 1, cy - 1),
                          (cx + THUMB_W, cy + THUMB_H), bc, bt)
            cv2.putText(canvas, lbl, (cx, cy + THUMB_H + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

    bar_y = WIN_H - BOTTOM_H
    cv2.rectangle(canvas, (0, bar_y), (WIN_W, WIN_H), (20, 20, 20), -1)
    n   = len(selected)
    msg = f"Selected: {n}  |  Click: toggle  |  W/S / Wheel: scroll  |  Enter: confirm"
    cv2.putText(canvas, msg, (PAD, bar_y + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                (0, 220, 100) if n else (100, 100, 255), 1)
    return canvas
