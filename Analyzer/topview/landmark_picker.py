import cv2
from topview.field_landmarks import LANDMARKS

# 한글 윈도우 이름은 Windows OpenCV에서 namedWindow/imshow 불일치를 유발함
WINDOW = "MatchVision - Pick Landmarks"


def pick_landmarks(frame) -> tuple[list[list[int]], list[list[float]]]:
    names = list(LANDMARKS.keys())

    print("\n=== 보이는 필드 마킹 선택 ===")
    for i, name in enumerate(names):
        mx, my = LANDMARKS[name]
        print(f"  {i+1:2d}. {name:<20} ({mx:5.1f}m, {my:5.1f}m)")

    print("\n보이는 마킹 4개의 번호를 입력하세요 (예: 1 5 8 12): ", end="")
    choices = list(map(int, input().split()))
    assert len(choices) == 4, "정확히 4개를 선택해야 합니다."

    selected_names = [names[c - 1] for c in choices]
    dst_points     = [list(LANDMARKS[n]) for n in selected_names]

    src_points = _click_points(frame, selected_names)
    return src_points, dst_points


def _click_points(frame, names: list[str]) -> list[list[int]]:
    # 화면에 맞게 축소 (클릭 좌표는 원본 해상도로 역변환)
    h, w = frame.shape[:2]
    scale = min(1280 / w, 720 / h, 1.0)
    display = cv2.resize(frame, (int(w * scale), int(h * scale)))

    clicked_original: list[list[int]] = []

    def on_mouse(event, x, y, _flags, _param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        # 표시된 좌표 → 원본 좌표
        ox, oy = int(x / scale), int(y / scale)
        clicked_original.append([ox, oy])

        cv2.circle(display, (x, y), 6, (0, 255, 255), -1)
        label = names[len(clicked_original) - 1]
        cv2.putText(display, label, (x + 8, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        _update_guide(display, names, len(clicked_original))
        cv2.imshow(WINDOW, display)

    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW, on_mouse)
    _update_guide(display, names, 0)
    cv2.imshow(WINDOW, display)

    while len(clicked_original) < len(names):
        if cv2.waitKey(30) & 0xFF == ord("q"):
            raise RuntimeError("사용자가 마킹 선택을 취소했습니다.")

    cv2.destroyWindow(WINDOW)
    return clicked_original


def _update_guide(frame, names: list[str], done: int):
    bar_w = min(500, frame.shape[1])
    overlay = frame[:40, :bar_w].copy()
    cv2.rectangle(frame, (0, 0), (bar_w, 40), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.35, frame[:40, :bar_w], 0.65, 0, frame[:40, :bar_w])

    if done < len(names):
        guide = f"Click: {names[done]}  ({done+1}/{len(names)})"
    else:
        guide = "Done! closing..."

    cv2.putText(frame, guide, (8, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
