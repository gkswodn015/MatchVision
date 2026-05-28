import sys
import os
import cv2

from topview.keyframe_selector import extract_keyframes, select_keyframes
from topview.landmark_picker import pick_landmarks
from topview.homography import HomographyMapper
from topview.calibration_set import CalibrationSet
from topview.coordinate_mapper import CoordinateMapper
from topview.field_landmarks import FIELD_W, FIELD_H
from detector.yolo_detector import YoloDetector
from detector.classifier import pick_role_samples
from pipeline.video_pipeline import VideoPipeline

DATA_DIR = "data"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}


def select_video() -> str:
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not os.path.isfile(path):
            print(f"파일을 찾을 수 없습니다: {path}")
            sys.exit(1)
        return path

    if not os.path.isdir(DATA_DIR):
        print(f"데이터 폴더가 없습니다: {DATA_DIR}")
        sys.exit(1)

    videos = sorted(
        f for f in os.listdir(DATA_DIR)
        if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
    )

    if not videos:
        print(f"{DATA_DIR}/ 폴더에 영상 파일이 없습니다.")
        sys.exit(1)

    if len(videos) == 1:
        path = os.path.join(DATA_DIR, videos[0])
        print(f"영상: {videos[0]}")
        return path

    print("\n분석할 영상을 선택하세요:")
    for i, name in enumerate(videos, 1):
        size_mb = os.path.getsize(os.path.join(DATA_DIR, name)) / (1024 * 1024)
        print(f"  [{i}] {name}  ({size_mb:.1f} MB)")
    print()

    while True:
        try:
            choice = input(f"번호 입력 (1-{len(videos)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(videos):
                return os.path.join(DATA_DIR, videos[idx])
        except (ValueError, KeyboardInterrupt):
            pass
        print(f"1~{len(videos)} 사이의 번호를 입력하세요.")


def main():
    video_path = select_video()

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()

    print("키프레임 추출 중...")
    keyframes = extract_keyframes(video_path)
    print(f"  {len(keyframes)}개 키프레임 추출 완료\n")

    selected = select_keyframes(keyframes, fps=fps)
    if not selected:
        print("선택된 프레임이 없습니다. 종료합니다.")
        sys.exit(0)

    print(f"\n{len(selected)}개 프레임의 앵커 포인트를 순서대로 지정하세요.")
    calibrations: list[tuple[int, HomographyMapper]] = []
    for i, (frame_idx, frame) in enumerate(selected):
        m, s = divmod(int(frame_idx / fps), 60)
        print(f"\n[{i + 1}/{len(selected)}] 프레임 {frame_idx}  ({m:02d}:{s:02d})")
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

    pipeline  = VideoPipeline(video_path, calib_set, classifier=classifier)
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
