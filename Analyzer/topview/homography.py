import cv2
import numpy as np


class HomographyMapper:
    """
    Convert image pixels to real pitch coordinates in meters.
    Four or more point pairs are enough because homography is estimated with RANSAC.
    CameraTracker can call update_H() every frame to compensate camera motion.
    """

    def __init__(self, src_points: list[list[float]], dst_points: list[list[float]]):
        self.src_points = np.float32(src_points)
        self.dst_points = np.float32(dst_points)
        H, mask = cv2.findHomography(self.src_points, self.dst_points, cv2.RANSAC, 5.0)
        if H is None:
            raise ValueError(
                "Homography calculation failed. Points may be collinear or duplicated."
            )
        self.H = H
        self._report_errors(self.src_points, self.dst_points, mask)

    def update_H(self, H: np.ndarray):
        """Update H to reflect camera motion tracked by CameraTracker."""
        self.H = H.astype(np.float32)

    def clone(self) -> "HomographyMapper":
        mapper = object.__new__(HomographyMapper)
        mapper.src_points = self.src_points.copy()
        mapper.dst_points = self.dst_points.copy()
        mapper.H = self.H.copy()
        return mapper

    def to_meters(self, pixel_x: int, pixel_y: int) -> tuple[float, float]:
        pt = np.float32([[[pixel_x, pixel_y]]])
        result = cv2.perspectiveTransform(pt, self.H)
        return float(result[0][0][0]), float(result[0][0][1])

    def _report_errors(self, src: np.ndarray, dst: np.ndarray, mask):
        projected = cv2.perspectiveTransform(src.reshape(-1, 1, 2), self.H)
        errors = np.linalg.norm(projected.reshape(-1, 2) - dst, axis=1)
        inliers = mask.ravel().astype(bool) if mask is not None else np.ones(len(errors), bool)
        print("\n=== Homography Calibration Result ===")
        for i, (err, ok) in enumerate(zip(errors, inliers)):
            tag = "" if ok else " (outlier)"
            print(f"  Point {i + 1}: {err:.3f}m{tag}")
        if inliers.any():
            print(f"  Mean error (inlier): {errors[inliers].mean():.3f}m")
