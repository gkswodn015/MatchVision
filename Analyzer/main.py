import sys
import cv2

from topview.landmark_picker import pick_landmarks
from topview.homography import HomographyMapper
from topview.coordinate_mapper import CoordinateMapper
from pipeline.video_pipeline import VideoPipeline

VIDEO_PATH = "data/test.mp4"


def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    ret, first_frame = cap.read()
    cap.release()

    if not ret:
        print(f"영상을 읽을 수 없습니다: {VIDEO_PATH}")
        sys.exit(1)

    src_points, dst_points = pick_landmarks(first_frame)

    mapper       = HomographyMapper(src_points, dst_points)
    coord_mapper = CoordinateMapper(mapper)

    pipeline = VideoPipeline(VIDEO_PATH, coord_mapper)
    pipeline.run()


if __name__ == "__main__":
    main()
