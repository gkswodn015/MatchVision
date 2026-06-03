from ultralytics import YOLO


class YoloDetector:
    ALLOWED_CLASSES = {"person", "sports ball"}

    def __init__(
        self,
        model_path: str = "yolov8x.pt",
        conf: float = 0.25,
        imgsz: int = 1280,
        tile: bool = False,
        tile_size: int = 1280,
        tile_overlap: float = 0.2,
    ):
        self.model = YOLO(model_path)
        self.conf = conf
        self.imgsz = imgsz
        self.tile = tile
        self.tile_size = tile_size
        self.tile_overlap = tile_overlap

    # ------------------------------------------------------------------
    def detect(self, frame) -> list[dict]:
        if self.tile:
            return self._detect_tiled(frame)
        return self._detect_full(frame)

    # ------------------------------------------------------------------
    def _detect_full(self, frame) -> list[dict]:
        results = self.model(frame, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        return self._parse(results, 0, 0)

    def _detect_tiled(self, frame) -> list[dict]:
        h, w = frame.shape[:2]
        step = int(self.tile_size * (1 - self.tile_overlap))

        all_dets: list[dict] = []
        y = 0
        while True:
            y_end = min(y + self.tile_size, h)
            x = 0
            while True:
                x_end = min(x + self.tile_size, w)
                tile = frame[y:y_end, x:x_end]
                results = self.model(
                    tile, conf=self.conf, imgsz=self.tile_size, verbose=False
                )[0]
                all_dets.extend(self._parse(results, x, y))
                if x_end == w:
                    break
                x = min(x + step, w - self.tile_size)
            if y_end == h:
                break
            y = min(y + step, h - self.tile_size)

        return _nms(all_dets)

    # ------------------------------------------------------------------
    def _parse(self, results, off_x: int, off_y: int) -> list[dict]:
        dets = []
        for box in results.boxes:
            cls = self.model.names[int(box.cls[0])]
            if cls not in self.ALLOWED_CLASSES:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            dets.append({
                "bbox":  [x1 + off_x, y1 + off_y, x2 + off_x, y2 + off_y],
                "class": cls,
                "conf":  float(box.conf[0]),
            })
        return dets


# ── 모듈 레벨 NMS (타일 간 중복 bbox 제거) ──────────────────────────────

def _iou(a: list[int], b: list[int]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def _nms(dets: list[dict], iou_thr: float = 0.45) -> list[dict]:
    dets = sorted(dets, key=lambda d: d["conf"], reverse=True)
    kept: list[dict] = []
    for d in dets:
        if not any(_iou(d["bbox"], k["bbox"]) > iou_thr for k in kept):
            kept.append(d)
    return kept
