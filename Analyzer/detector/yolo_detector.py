from ultralytics import YOLO


class YoloDetector:
    ALLOWED_CLASSES = {"person", "sports ball"}

    def __init__(self, model_path: str = "yolov8x.pt", conf: float = 0.3):
        self.model = YOLO(model_path)
        self.conf = conf

    def detect(self, frame) -> list[dict]:
        results = self.model(frame, conf=self.conf, verbose=False)[0]

        detections = []
        for box in results.boxes:
            class_name = self.model.names[int(box.cls[0])]
            if class_name not in self.ALLOWED_CLASSES:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            detections.append({
                "bbox":  [x1, y1, x2, y2],
                "class": class_name,
                "conf":  float(box.conf[0]),
            })

        return detections
