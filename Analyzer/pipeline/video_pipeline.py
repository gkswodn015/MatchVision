import cv2
import numpy as np

from detector.yolo_detector import YoloDetector
from tracker.bytetrack import ByteTracker
from topview.coordinate_mapper import CoordinateMapper, CANVAS_W, CANVAS_H
from topview.field_landmarks import FIELD_W, FIELD_H
from stats.speed_calculator import SpeedCalculator
from stats.possession import PossessionTracker
from visualizer.overlay import draw_tracks, draw_topview_dots
from visualizer.path_drawer import PathDrawer


class VideoPipeline:
    def __init__(self, video_path: str, coord_mapper: CoordinateMapper):
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise FileNotFoundError(f"영상을 열 수 없습니다: {video_path}")

        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.coord_mapper = coord_mapper

        self.detector   = YoloDetector()
        self.tracker    = ByteTracker()
        self.speed_calc = SpeedCalculator(fps=self.fps)
        self.possession = PossessionTracker()
        self.path_drawer = PathDrawer()

        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.display_scale = min(1280 / w, 720 / h)

    def run(self):
        print("분석 시작. 'q' 키로 종료.\n")

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            # --- 탐지 & 추적 ---
            detections = self.detector.detect(frame)
            tracks     = self.tracker.update(detections)

            # --- 좌표 변환 ---
            positions = []
            for t in tracks:
                mx, my = self.coord_mapper.to_meters(t["bbox"])
                cx, cy = self.coord_mapper.to_canvas(t["bbox"])
                positions.append({"id": t["id"], "mx": mx, "my": my, "cx": cx, "cy": cy})

            # --- 통계 ---
            speed_stats = self.speed_calc.update(positions)
            self.possession.update(tracks, positions)

            # --- 탑뷰 ---
            topview = self._make_topview_canvas()
            self.path_drawer.update(positions)
            self.path_drawer.draw(topview)
            draw_topview_dots(topview, positions, tracks)

            # --- 원본 프레임 ---
            draw_tracks(frame, tracks, speed_stats)

            # --- 출력 ---
            display = cv2.resize(frame, (
                int(frame.shape[1] * self.display_scale),
                int(frame.shape[0] * self.display_scale),
            ))
            cv2.imshow("MatchVision - Original", display)
            cv2.imshow("MatchVision - TopView",  topview)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        self._cleanup()

    def _make_topview_canvas(self) -> np.ndarray:
        canvas = np.full((CANVAS_H, CANVAS_W, 3), (34, 139, 34), dtype=np.uint8)
        # 외곽선
        cv2.rectangle(canvas, (0, 0), (CANVAS_W - 1, CANVAS_H - 1), (255, 255, 255), 2)
        # 하프라인
        half_x = int(52.5 * CANVAS_W / FIELD_W)
        cv2.line(canvas, (half_x, 0), (half_x, CANVAS_H), (255, 255, 255), 1)
        # 센터서클 (반지름 9.15m)
        r = int(9.15 * CANVAS_W / FIELD_W)
        cv2.circle(canvas, (half_x, CANVAS_H // 2), r, (255, 255, 255), 1)
        # 페널티박스
        self._draw_box(canvas,  0.0, 13.84, 16.5, 54.16)
        self._draw_box(canvas, 88.5, 13.84, 105.0, 54.16)
        return canvas

    def _draw_box(self, canvas, mx1, my1, mx2, my2):
        x1 = int(mx1 * CANVAS_W / FIELD_W)
        y1 = int(my1 * CANVAS_H / FIELD_H)
        x2 = int(mx2 * CANVAS_W / FIELD_W)
        y2 = int(my2 * CANVAS_H / FIELD_H)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (255, 255, 255), 1)

    def _cleanup(self):
        self.cap.release()
        cv2.destroyAllWindows()

        ratios = self.possession._ratios()
        if ratios:
            print("\n=== 점유율 ===")
            for tid, ratio in sorted(ratios.items(), key=lambda x: -x[1]):
                print(f"  ID {tid:3d}: {ratio*100:.1f}%")
