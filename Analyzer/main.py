import os
import sys
import cv2

from detector.classifier import pick_role_samples
from detector.yolo_detector import YoloDetector
from pipeline.video_pipeline import VideoPipeline
from topview.calibration_set import CalibrationSet
from topview.coordinate_mapper import CoordinateMapper
from topview.field_landmarks import FIELD_H, FIELD_W
from topview.homography import HomographyMapper
from topview.keyframe_selector import select_keyframes_from_video
from topview.landmark_picker import pick_landmarks

DATA_DIR = "data"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}


def select_video() -> str:
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not os.path.isfile(path):
            print(f"File not found: {path}")
            sys.exit(1)
        return path

    if not os.path.isdir(DATA_DIR):
        print(f"Data folder not found: {DATA_DIR}")
        sys.exit(1)

    videos = sorted(
        f for f in os.listdir(DATA_DIR)
        if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
    )

    if not videos:
        print(f"No video files found in {DATA_DIR}/")
        sys.exit(1)

    if len(videos) == 1:
        path = os.path.join(DATA_DIR, videos[0])
        print(f"Video: {videos[0]}")
        return path

    print("\nSelect a video to analyze:")
    for i, name in enumerate(videos, 1):
        size_mb = os.path.getsize(os.path.join(DATA_DIR, name)) / (1024 * 1024)
        print(f"  [{i}] {name}  ({size_mb:.1f} MB)")
    print()

    while True:
        try:
            choice = input(f"Number (1-{len(videos)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(videos):
                return os.path.join(DATA_DIR, videos[idx])
        except (ValueError, KeyboardInterrupt):
            pass
        print(f"Enter a number between 1 and {len(videos)}.")


def main():
    video_path = select_video()

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()

    print("Move through the video and capture frames where the camera angle changes.")
    selected = select_keyframes_from_video(video_path)
    if not selected:
        print("No calibration frames selected. Exiting.")
        sys.exit(0)

    print(f"\nPick anchor points for {len(selected)} selected frame(s).")
    calibrations: list[tuple[int, HomographyMapper]] = []
    for i, (frame_idx, frame) in enumerate(selected):
        m, s = divmod(int(frame_idx / fps), 60)
        print(f"\n[{i + 1}/{len(selected)}] frame {frame_idx}  ({m:02d}:{s:02d})")
        src_pts, dst_pts = pick_landmarks(frame)
        calibrations.append((frame_idx, HomographyMapper(src_pts, dst_pts)))

    calib_set = CalibrationSet(calibrations)
    sample_frame_idx, sample_frame = selected[0]
    sample_mapper = CoordinateMapper(calib_set.get_mapper(sample_frame_idx))

    print("\nDetecting players for role samples...")
    detector = YoloDetector()
    raw_sample_detections = detector.detect(sample_frame)
    sample_detections = _filter_inside_field(raw_sample_detections, sample_mapper)
    if sum(1 for det in sample_detections if det["class"] == "person") < 3:
        sample_detections = raw_sample_detections

    print("Click one OUR TEAM player, one OPPONENT player, and one REFEREE.")
    classifier = pick_role_samples(sample_frame, sample_detections)

    pipeline = VideoPipeline(video_path, calib_set, classifier=classifier)
    pipeline.run()


def _filter_inside_field(detections: list[dict], mapper: CoordinateMapper) -> list[dict]:
    filtered = []
    margin = 1.0
    for det in detections:
        try:
            mx, my = mapper.to_meters(det["bbox"])
        except cv2.error:
            continue
        if -margin <= mx <= FIELD_W + margin and -margin <= my <= FIELD_H + margin:
            filtered.append(det)
    return filtered


if __name__ == "__main__":
    main()
