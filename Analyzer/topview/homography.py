import cv2
import numpy as np


class HomographyMapper:
    """
    픽셀 좌표 → 실제 경기장 좌표(미터) 변환.
    4개 이상의 대응점을 RANSAC으로 계산하므로 택티컬캠처럼
    4 코너 전부가 보이지 않는 경우에도 동작한다.
    CameraTracker가 매 프레임 update_H()를 호출해 카메라 이동을 보정한다.
    """

    def __init__(self, src_points: list[list[float]], dst_points: list[list[float]]):
        self.src_points = np.float32(src_points)
        self.dst_points = np.float32(dst_points)
        H, mask = cv2.findHomography(self.src_points, self.dst_points, cv2.RANSAC, 5.0)
        if H is None:
            raise ValueError(
                "호모그래피 계산 실패 — 점들이 선형이거나 중복되었습니다."
            )
        self.H = H
        self._report_errors(self.src_points, self.dst_points, mask)

    def update_H(self, H: np.ndarray):
        """CameraTracker가 매 프레임 호출해 카메라 이동을 반영한다."""
        self.H = H.astype(np.float32)

    def to_meters(self, pixel_x: int, pixel_y: int) -> tuple[float, float]:
        pt = np.float32([[[pixel_x, pixel_y]]])
        result = cv2.perspectiveTransform(pt, self.H)
        return float(result[0][0][0]), float(result[0][0][1])

    def _report_errors(self, src: np.ndarray, dst: np.ndarray, mask):
        projected = cv2.perspectiveTransform(src.reshape(-1, 1, 2), self.H)
        errors = np.linalg.norm(projected.reshape(-1, 2) - dst, axis=1)
        inliers = mask.ravel().astype(bool) if mask is not None else np.ones(len(errors), bool)
        print("\n=== 호모그래피 보정 결과 ===")
        for i, (err, ok) in enumerate(zip(errors, inliers)):
            tag = "" if ok else " (outlier)"
            print(f"  점 {i + 1}: {err:.3f}m{tag}")
        if inliers.any():
            print(f"  평균 오차 (inlier): {errors[inliers].mean():.3f}m")
