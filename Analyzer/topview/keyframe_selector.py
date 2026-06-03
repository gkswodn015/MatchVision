import cv2
import numpy as np

WIN = "Calibration Frame Picker"
TRACKBAR = "frame"
MAX_W = 1280
MAX_H = 720
BAR_H = 86


def select_keyframes_from_video(video_path: str) -> list[tuple[int, np.ndarray]]:
    """
    Slider UI for selecting calibration frames.

    Controls:
      - Trackbar: move through the video
      - A/D: previous/next frame
      - W/S: jump backward/forward 1 second
      - Space/C: capture current frame
      - Backspace/Delete: remove latest captured frame
      - Enter: confirm selected frames
      - ESC/Q: cancel
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []

    selected: dict[int, np.ndarray] = {}
    current = [0]
    last_drawn = [-1]

    cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)

    def on_trackbar(value):
        current[0] = max(0, min(total - 1, value))

    cv2.createTrackbar(TRACKBAR, WIN, 0, total - 1, on_trackbar)

    while True:
        frame_idx = current[0]
        if frame_idx != last_drawn[0]:
            frame = _read_frame(cap, frame_idx)
            if frame is not None:
                cv2.imshow(WIN, _render(frame, frame_idx, fps, total, selected))
                last_drawn[0] = frame_idx

        key = cv2.waitKey(30) & 0xFF
        if key == 255:
            continue

        if key in (27, ord("q"), ord("Q")):
            selected.clear()
            break
        if key in (13, 10):
            if selected:
                break
            continue
        if key in (ord(" "), ord("c"), ord("C")):
            frame = _read_frame(cap, frame_idx)
            if frame is not None:
                selected[frame_idx] = frame.copy()
                last_drawn[0] = -1
            continue
        if key in (8, 127):
            if selected:
                selected.pop(sorted(selected)[-1], None)
                last_drawn[0] = -1
            continue

        next_idx = frame_idx
        if key in (ord("a"), ord("A")):
            next_idx = frame_idx - 1
        elif key in (ord("d"), ord("D")):
            next_idx = frame_idx + 1
        elif key in (ord("w"), ord("W")):
            next_idx = frame_idx - int(fps)
        elif key in (ord("s"), ord("S")):
            next_idx = frame_idx + int(fps)

        next_idx = max(0, min(total - 1, next_idx))
        if next_idx != frame_idx:
            current[0] = next_idx
            cv2.setTrackbarPos(TRACKBAR, WIN, next_idx)

    cap.release()
    cv2.destroyWindow(WIN)
    return [(idx, selected[idx]) for idx in sorted(selected)]


def _read_frame(cap: cv2.VideoCapture, frame_idx: int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    return frame if ret else None


def _render(
    frame,
    frame_idx: int,
    fps: float,
    total: int,
    selected: dict[int, np.ndarray],
) -> np.ndarray:
    h, w = frame.shape[:2]
    scale = min(MAX_W / w, MAX_H / h, 1.0)
    view = cv2.resize(frame, (int(w * scale), int(h * scale)))

    canvas = np.full((view.shape[0] + BAR_H, view.shape[1], 3), (24, 24, 24), dtype=np.uint8)
    canvas[:view.shape[0], :view.shape[1]] = view

    y0 = view.shape[0]
    seconds = frame_idx / fps
    m, s = divmod(int(seconds), 60)
    count = len(selected)

    cv2.rectangle(canvas, (0, y0), (canvas.shape[1], canvas.shape[0]), (18, 18, 18), -1)
    cv2.putText(canvas, f"Frame {frame_idx}/{total - 1}  Time {m:02d}:{s:02d}  Selected {count}",
                (10, y0 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (230, 230, 230), 2)
    cv2.putText(canvas, "Slider: seek | Space/C: capture | Backspace: undo | Enter: confirm | A/D: frame | W/S: 1 sec",
                (10, y0 + 52), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (170, 220, 170), 1)

    _draw_selected_ticks(canvas, y0 + 68, total, selected)
    return canvas


def _draw_selected_ticks(canvas, y: int, total: int, selected: dict[int, np.ndarray]):
    x1, x2 = 10, canvas.shape[1] - 10
    cv2.line(canvas, (x1, y), (x2, y), (80, 80, 80), 2)
    if total <= 1:
        return

    for idx in selected:
        x = int(x1 + (x2 - x1) * idx / (total - 1))
        cv2.line(canvas, (x, y - 8), (x, y + 8), (0, 220, 80), 2)
