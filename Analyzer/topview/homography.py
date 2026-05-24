import cv2
import numpy as np


class HomographyMapper:
    """
    픽셀 좌표 → 실제 경기장 좌표(미터) 변환.
    src: 영상에서 클릭한 4 코너 픽셀 좌표
    dst: 경기장 4 코너 실제 좌표(미터)
    4 코너 전체가 항상 보이는 영상을 전제로 하며, 이 경우 호모그래피가
    필드 전체를 정의역으로 가져 외삽 오차가 발생하지 않는다.
    """

    def __init__(self, src_points: list[list[float]], dst_points: list[list[float]]):
        src = np.float32(src_points)
        dst = np.float32(dst_points)
        self.H, _ = cv2.findHomography(src, dst)
        self._report_errors(src, dst)

    def _report_errors(self, src: np.ndarray, dst: np.ndarray):
        projected = cv2.perspectiveTransform(src.reshape(-1, 1, 2), self.H)
        errors = np.linalg.norm(projected.reshape(-1, 2) - dst, axis=1)
        print("\n=== 호모그래피 보정 결과 ===")
        labels = ["좌상", "우상", "우하", "좌하"]
        for label, err in zip(labels, errors):
            print(f"  {label} 코너: {err:.3f}m")
        print(f"  평균 오차: {errors.mean():.3f}m")

    def to_meters(self, pixel_x: int, pixel_y: int) -> tuple[float, float]:
        pt = np.float32([[[pixel_x, pixel_y]]])
        result = cv2.perspectiveTransform(pt, self.H)
        mx, my = result[0][0]
        return float(mx), float(my)
