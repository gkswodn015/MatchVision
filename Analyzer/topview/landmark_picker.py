import cv2
import numpy as np
from topview.field_landmarks import FIELD_H, FIELD_W, LANDMARKS

WINDOW = "MatchVision - Landmark Selection"

_PAD = 22
_SCALE = 4.0
_DIAG_W = int(FIELD_W * _SCALE) + 2 * _PAD
_DIAG_H = int(FIELD_H * _SCALE) + 2 * _PAD

_ZOOM_SZ = 140
_ZOOM_FAC = 5
_HIT_R = 24

_LM_LIST = list(LANDMARKS.items())


def _m2d(mx: float, my: float) -> tuple[int, int]:
    """Convert field meters to diagram-canvas pixels."""
    return _PAD + int(mx * _SCALE), _PAD + int(my * _SCALE)


def _nearest_lm(dx: int, dy: int, used: set) -> tuple | None:
    """Return the nearest unused landmark within the diagram click radius."""
    best_d, best = _HIT_R + 1, None
    for name, (mx, my) in _LM_LIST:
        if name in used:
            continue
        px, py = _m2d(mx, my)
        d = ((dx - px) ** 2 + (dy - py) ** 2) ** 0.5
        if d < best_d:
            best_d, best = d, (name, (mx, my))
    return best


def _make_diagram(confirmed: set, hover: str | None = None) -> np.ndarray:
    c = np.full((_DIAG_H, _DIAG_W, 3), (20, 80, 20), dtype=np.uint8)
    x0, y0 = _PAD, _PAD
    x1, y1 = _DIAG_W - _PAD - 1, _DIAG_H - _PAD - 1

    cv2.rectangle(c, (x0, y0), (x1, y1), (34, 139, 34), -1)
    cv2.rectangle(c, (x0, y0), (x1, y1), (255, 255, 255), 2)

    hx = _PAD + int(FIELD_W / 2 * _SCALE)
    cv2.line(c, (hx, y0), (hx, y1), (255, 255, 255), 1)
    cx, cy = _m2d(FIELD_W / 2, FIELD_H / 2)
    cv2.circle(c, (cx, cy), int(9.15 * _SCALE), (255, 255, 255), 1)
    cv2.circle(c, (cx, cy), 3, (255, 255, 255), -1)

    for bx0, bx1 in ((0.0, 16.5), (88.5, 105.0)):
        a, b = _m2d(bx0, 13.84)
        d, e = _m2d(bx1, 54.16)
        cv2.rectangle(c, (a, b), (d, e), (255, 255, 255), 1)

    for gx0, gx1 in ((0.0, 5.5), (99.5, 105.0)):
        a, b = _m2d(gx0, 24.84)
        d, e = _m2d(gx1, 43.16)
        cv2.rectangle(c, (a, b), (d, e), (255, 255, 255), 1)

    for mx, my in ((11.0, 34.0), (94.0, 34.0)):
        cv2.circle(c, _m2d(mx, my), 3, (255, 255, 255), -1)

    for i, (name, (mx, my)) in enumerate(_LM_LIST):
        px, py = _m2d(mx, my)
        if name in confirmed:
            col, r = (50, 255, 80), 6
        elif name == hover:
            col, r = (50, 255, 255), 8
        else:
            col, r = (80, 180, 255), 5
        cv2.circle(c, (px, py), r, col, -1)
        cv2.circle(c, (px, py), r, (0, 0, 0), 1)
        cv2.putText(c, str(i + 1), (px + 5, py + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, (255, 255, 255), 1)

    cv2.rectangle(c, (0, 0), (_DIAG_W, 18), (10, 50, 10), -1)
    cv2.putText(c, " <- click matching landmark", (4, 13),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 220, 180), 1)
    return c


def _draw_zoom(panel: np.ndarray, cx: int, cy: int):
    ph, pw = panel.shape[:2]
    half = _ZOOM_SZ // (2 * _ZOOM_FAC)
    x1, y1 = max(0, cx - half), max(0, cy - half)
    x2, y2 = min(pw, cx + half), min(ph, cy + half)
    if x2 <= x1 or y2 <= y1:
        return
    zoomed = cv2.resize(panel[y1:y2, x1:x2], (_ZOOM_SZ, _ZOOM_SZ),
                        interpolation=cv2.INTER_LINEAR)
    mid = _ZOOM_SZ // 2
    cv2.line(zoomed, (mid, 0), (mid, _ZOOM_SZ - 1), (0, 255, 0), 1)
    cv2.line(zoomed, (0, mid), (_ZOOM_SZ - 1, mid), (0, 255, 0), 1)
    cv2.rectangle(zoomed, (0, 0), (_ZOOM_SZ - 1, _ZOOM_SZ - 1), (0, 255, 0), 2)
    ox = pw - _ZOOM_SZ - 6
    oy = 22
    if oy + _ZOOM_SZ <= ph and ox >= 0:
        panel[oy:oy + _ZOOM_SZ, ox:ox + _ZOOM_SZ] = zoomed


def pick_landmarks(frame: np.ndarray) -> tuple[list[list[int]], list[list[float]]]:
    """
    Two-panel UI: pair visible field markings with known FIFA landmarks.
    Works with tactical-cam frames where 4 corners are not all visible.
    """
    print("\n=== Field Landmark Selection ===")
    print("  Step 1: click a field-line intersection in the video panel.")
    print("  Step 2: click the matching point in the pitch diagram.")
    print("  Select at least 4 pairs, then press Enter or Q. Backspace: undo.\n")
    print("  Landmark list:")
    for i, (name, (mx, my)) in enumerate(_LM_LIST):
        print(f"    {i + 1:2d}. {name} ({mx:.1f}m, {my:.1f}m)")
    print()

    h, w = frame.shape[:2]
    vs = min(820 / w, 500 / h, 1.0)
    vw, vh = int(w * vs), int(h * vs)
    vid_base = cv2.resize(frame, (vw, vh))

    status_h = 34
    win_w = vw + _DIAG_W
    win_h = max(vh, _DIAG_H) + status_h

    pairs: list[tuple[list[int], str, list[float]]] = []
    confirmed: set[str] = set()
    st = {"phase": 0, "pend": None}
    hover: list[str | None] = [None]

    def _rebuild() -> np.ndarray:
        c = np.zeros((win_h, win_w, 3), dtype=np.uint8)

        vid = vid_base.copy()
        for i, (sp, name, _) in enumerate(pairs):
            cv2.circle(vid, tuple(sp), 6, (50, 255, 50), -1)
            cv2.circle(vid, tuple(sp), 6, (0, 0, 0), 1)
            cv2.putText(vid, str(i + 1), (sp[0] + 7, sp[1] - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (50, 255, 50), 2)
        if st["pend"] is not None:
            p = st["pend"]
            cv2.circle(vid, tuple(p), 7, (0, 200, 255), -1)
            cv2.circle(vid, tuple(p), 7, (0, 0, 0), 1)
            cv2.putText(vid, "?", (p[0] + 8, p[1] - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2)
        c[:vh, :vw] = vid

        c[:_DIAG_H, vw:vw + _DIAG_W] = _make_diagram(confirmed, hover[0])
        cv2.line(c, (vw, 0), (vw, win_h), (80, 80, 80), 1)

        sb = c[win_h - status_h:]
        sb[:] = (20, 20, 20)
        if st["phase"] == 0:
            msg = (f"[{len(pairs)} pairs] Step 1: click video field point"
                   f" | Enter({len(pairs)}/4+): confirm  Backspace: undo")
        else:
            msg = (f"[{len(pairs)} pairs] Step 2: click diagram landmark"
                   f" | Backspace: undo")
        cv2.putText(sb, msg, (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 220, 220), 1)
        return c

    img = [_rebuild()]

    def on_mouse(event, x, y, flags, _):
        in_vid = x < vw and y < vh
        in_diag = x >= vw and y < _DIAG_H
        dx, dy = x - vw, y

        if event == cv2.EVENT_MOUSEMOVE:
            vis = img[0].copy()
            if in_vid:
                _draw_zoom(vis[:vh, :vw], x, y)
            if in_diag:
                match = _nearest_lm(dx, dy, confirmed)
                new_h = match[0] if match else None
            else:
                new_h = None
            if new_h != hover[0]:
                hover[0] = new_h
                img[0] = _rebuild()
                vis = img[0].copy()
                if in_vid:
                    _draw_zoom(vis[:vh, :vw], x, y)
            cv2.imshow(WINDOW, vis)
            return

        if event != cv2.EVENT_LBUTTONDOWN:
            return

        if in_vid:
            st["pend"] = [x, y]
            st["phase"] = 1
            img[0] = _rebuild()
            cv2.imshow(WINDOW, img[0])

        elif in_diag and st["phase"] == 1:
            match = _nearest_lm(dx, dy, confirmed)
            if match is not None:
                name, (mx, my) = match
                pairs.append((st["pend"].copy(), name, [mx, my]))
                confirmed.add(name)
                st["pend"] = None
                st["phase"] = 0
                print(f"  [{len(pairs)}] {name} -> ({mx:.1f}m, {my:.1f}m)")
                img[0] = _rebuild()
                cv2.imshow(WINDOW, img[0])

    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW, on_mouse)
    cv2.imshow(WINDOW, img[0])

    while True:
        key = cv2.waitKey(30) & 0xFF
        if key in (13, ord('q'), 27) and len(pairs) >= 4:
            break
        if key in (8, 127):
            if st["phase"] == 1:
                st["pend"] = None
                st["phase"] = 0
            elif pairs:
                _, removed, _ = pairs.pop()
                confirmed.discard(removed)
                print(f"  Undo -> {len(pairs)} pair(s) remaining")
            img[0] = _rebuild()
            cv2.imshow(WINDOW, img[0])

    cv2.destroyWindow(WINDOW)

    src_points = [[int(sp[0] / vs), int(sp[1] / vs)] for sp, _, _ in pairs]
    dst_points = [d for _, _, d in pairs]
    return src_points, dst_points
