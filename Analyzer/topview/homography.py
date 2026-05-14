import cv2
import numpy as np


class HomographyMapper:
    """
    픽셀 좌표 → 실제 경기장 좌표(미터) 변환.
    src: 영상에서 클릭한 픽셀 좌표 4점
    dst: field_landmarks 의 실제 좌표(미터) 4점
    """

    def __init__(self, src_points: list[list[float]], dst_points: list[list[float]]):
        src = np.float32(src_points)
        dst = np.float32(dst_points)
        self.H, _ = cv2.findHomography(src, dst)

    def to_meters(self, pixel_x: int, pixel_y: int) -> tuple[float, float]:
        pt = np.float32([[[pixel_x, pixel_y]]])
        result = cv2.perspectiveTransform(pt, self.H)
        mx, my = result[0][0]
        return float(mx), float(my)
