from topview.homography import HomographyMapper
from topview.field_landmarks import FIELD_W, FIELD_H

CANVAS_W = 640
CANVAS_H = 420
CANVAS_PAD_X = 18
CANVAS_PAD_Y = 18


class CoordinateMapper:
    """
    bbox → 실제 경기장 좌표(미터) → 탑뷰 캔버스 픽셀 좌표 변환.
    """

    def __init__(self, mapper: HomographyMapper):
        self.mapper = mapper

    def to_meters(self, bbox: list[int]) -> tuple[float, float]:
        x1, _, x2, y2 = bbox
        foot_x = (x1 + x2) // 2
        foot_y = y2
        return self.mapper.to_meters(foot_x, foot_y)

    def to_canvas(self, bbox: list[int]) -> tuple[int, int]:
        mx, my = self.to_meters(bbox)
        pitch_w = CANVAS_W - CANVAS_PAD_X * 2
        pitch_h = CANVAS_H - CANVAS_PAD_Y * 2
        cx = int(CANVAS_PAD_X + mx * pitch_w / FIELD_W)
        cy = int(CANVAS_PAD_Y + my * pitch_h / FIELD_H)
        return cx, cy
