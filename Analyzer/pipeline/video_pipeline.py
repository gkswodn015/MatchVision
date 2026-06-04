import os

import cv2
import numpy as np

from detector.yolo_detector import YoloDetector
from detector.classifier import TeamClassifier
from tracker.bytetrack import ByteTracker
from topview.coordinate_mapper import (
    CANVAS_H,
    CANVAS_PAD_X,
    CANVAS_PAD_Y,
    CANVAS_W,
    CoordinateMapper,
)
from topview.calibration_set import CalibrationSet
from topview.field_landmarks import FIELD_W, FIELD_H
from stats.speed_calculator import SpeedCalculator
from stats.possession import PossessionTracker
from visualizer.overlay import draw_tracks, draw_topview_dots


class VideoPipeline:
    def __init__(
        self,
        video_path: str,
        calib_set: CalibrationSet,
        classifier: TeamClassifier | None = None,
        display: bool = True,
        result_dir: str | None = None,
    ):
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {video_path}")

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.calib_set = calib_set
        self.coord_mapper = CoordinateMapper(calib_set.get_mapper(0))
        self.display = display

        self.detector = YoloDetector()
        self.classifier = classifier or TeamClassifier()
        self.tracker = ByteTracker()
        self.speed_calc = SpeedCalculator(fps=self.fps)
        self.possession = PossessionTracker()

        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_size = (w, h)
        self.display_scale = min(1280 / w, 720 / h)

        self.result_dir = result_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "result",
        )
        os.makedirs(self.result_dir, exist_ok=True)

        video_name = os.path.splitext(os.path.basename(video_path))[0]
        self.detected_path = os.path.join(self.result_dir, f"{video_name}_detected.mp4")
        self.topview_path = os.path.join(self.result_dir, f"{video_name}_topview.mp4")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.detected_writer = cv2.VideoWriter(
            self.detected_path,
            fourcc,
            self.fps,
            self.frame_size,
        )
        self.topview_writer = cv2.VideoWriter(
            self.topview_path,
            fourcc,
            self.fps,
            (CANVAS_W, CANVAS_H),
        )

        if not self.detected_writer.isOpened():
            raise RuntimeError(f"Failed to create output video: {self.detected_path}")
        if not self.topview_writer.isOpened():
            raise RuntimeError(f"Failed to create output video: {self.topview_path}")

    def run(self):
        print("Analysis started. Press 'q' to stop.\n")

        frame_n = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame_n += 1

            self.coord_mapper.mapper = self.calib_set.get_mapper(frame_n)

            raw_detections = self.detector.detect(frame)
            detections = self._filter_inside_field(raw_detections)
            detections = self.classifier.classify(frame, detections)
            tracks = self.tracker.update(detections)

            positions = []
            for t in tracks:
                mx, my = self.coord_mapper.to_meters(t["bbox"])
                cx, cy = self.coord_mapper.to_canvas(t["bbox"])
                positions.append({"id": t["id"], "mx": mx, "my": my, "cx": cx, "cy": cy})

            speed_stats = self.speed_calc.update(positions)
            self.possession.update(tracks, positions)

            topview = self._make_topview_canvas()
            draw_topview_dots(topview, positions, tracks)

            draw_tracks(frame, tracks, speed_stats)
            self.detected_writer.write(frame)
            self.topview_writer.write(topview)

            if self.display:
                display = cv2.resize(frame, (
                    int(frame.shape[1] * self.display_scale),
                    int(frame.shape[0] * self.display_scale),
                ))
                cv2.imshow("MatchVision - Original", display)
                cv2.imshow("MatchVision - TopView", topview)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        self._cleanup()
        return {
            "detected_path": self.detected_path,
            "topview_path": self.topview_path,
        }

    def _make_topview_canvas(self) -> np.ndarray:
        canvas = np.full((CANVAS_H, CANVAS_W, 3), (24, 118, 28), dtype=np.uint8)

        stripe_w = max(1, CANVAS_W // 12)
        for i in range(12):
            if i % 2 == 0:
                x1 = i * stripe_w
                x2 = CANVAS_W if i == 11 else (i + 1) * stripe_w
                cv2.rectangle(canvas, (x1, 0), (x2, CANVAS_H), (30, 132, 34), -1)

        line = (235, 245, 235)
        cv2.rectangle(
            canvas,
            (CANVAS_PAD_X, CANVAS_PAD_Y),
            (CANVAS_W - CANVAS_PAD_X, CANVAS_H - CANVAS_PAD_Y),
            line,
            3,
            cv2.LINE_AA,
        )

        half_x, half_y = self._to_canvas_point(52.5, 34.0)
        cv2.line(
            canvas,
            (half_x, CANVAS_PAD_Y),
            (half_x, CANVAS_H - CANVAS_PAD_Y),
            line,
            3,
            cv2.LINE_AA,
        )
        pitch_w = CANVAS_W - CANVAS_PAD_X * 2
        r = int(9.15 * pitch_w / FIELD_W)
        cv2.circle(canvas, (half_x, half_y), r, line, 3, cv2.LINE_AA)
        cv2.circle(canvas, (half_x, half_y), 4, line, -1, cv2.LINE_AA)

        self._draw_box(canvas, 0.0, 13.84, 16.5, 54.16)
        self._draw_box(canvas, 88.5, 13.84, 105.0, 54.16)
        self._draw_box(canvas, 0.0, 24.84, 5.5, 43.16)
        self._draw_box(canvas, 99.5, 24.84, 105.0, 43.16)

        cv2.circle(canvas, self._to_canvas_point(11.0, 34.0), 4, line, -1, cv2.LINE_AA)
        cv2.circle(canvas, self._to_canvas_point(94.0, 34.0), 4, line, -1, cv2.LINE_AA)
        return canvas

    def _draw_box(self, canvas, mx1, my1, mx2, my2):
        x1, y1 = self._to_canvas_point(mx1, my1)
        x2, y2 = self._to_canvas_point(mx2, my2)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (235, 245, 235), 3, cv2.LINE_AA)

    @staticmethod
    def _to_canvas_point(mx: float, my: float) -> tuple[int, int]:
        pitch_w = CANVAS_W - CANVAS_PAD_X * 2
        pitch_h = CANVAS_H - CANVAS_PAD_Y * 2
        return (
            int(CANVAS_PAD_X + mx * pitch_w / FIELD_W),
            int(CANVAS_PAD_Y + my * pitch_h / FIELD_H),
        )

    def _filter_inside_field(self, detections: list[dict]) -> list[dict]:
        filtered = []
        margin = 1.0
        for det in detections:
            try:
                mx, my = self.coord_mapper.to_meters(det["bbox"])
            except cv2.error:
                continue

            if -margin <= mx <= FIELD_W + margin and -margin <= my <= FIELD_H + margin:
                filtered.append(det)
        return filtered

    def _cleanup(self):
        self.cap.release()
        self.detected_writer.release()
        self.topview_writer.release()
        if self.display:
            cv2.destroyAllWindows()

        print(f"\nSaved detected video: {self.detected_path}")
        print(f"Saved topview video:  {self.topview_path}")

        ratios = self.possession._ratios()
        if ratios:
            print("\n=== Possession ===")
            for tid, ratio in sorted(ratios.items(), key=lambda x: -x[1]):
                print(f"  ID {tid:3d}: {ratio*100:.1f}%")
