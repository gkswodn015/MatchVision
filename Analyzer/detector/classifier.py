
import cv2
import numpy as np

PICK_WINDOW = "Role Sample Picker"
ROLE_ORDER = [
    ("our_team", "OUR TEAM"),
    ("opponent", "OPPONENT"),
    ("referee", "REFEREE"),
]


class TeamClassifier:
    """
    Classifies person detections into our_team/opponent/referee using torso color.

    Without manual team samples there is no reliable way to know semantic
    "our team"; the initial assignment is deterministic: the color cluster whose
    players are more left-side on the first usable frame becomes our_team.
    """

    ROLE_COLORS = {
        "our_team": (255, 80, 40),
        "opponent": (40, 220, 255),
        "referee": (220, 40, 220),
        "sports ball": (0, 200, 255),
        "unknown": (200, 200, 200),
    }

    def __init__(self):
        self._prototypes: dict[str, np.ndarray] = {}
        self._manual_roles = False

    def set_prototypes(self, prototypes: dict[str, np.ndarray]):
        self._prototypes = {
            role: np.float32(feature).copy()
            for role, feature in prototypes.items()
        }
        self._manual_roles = all(role in self._prototypes for role, _ in ROLE_ORDER)

    def classify(self, frame, detections: list[dict]) -> list[dict]:
        persons: list[tuple[int, np.ndarray, float]] = []

        for i, det in enumerate(detections):
            if det["class"] == "sports ball":
                det["role"] = "sports ball"
                continue

            feature = self._torso_feature(frame, det["bbox"])
            if feature is None:
                det["role"] = "unknown"
                continue

            x1, _, x2, _ = det["bbox"]
            cx = (x1 + x2) / 2
            persons.append((i, feature, cx))

        if not persons:
            return detections

        if self._manual_roles:
            for i, feature, _ in persons:
                role = self._nearest_manual_role(feature)
                detections[i]["role"] = role
                self._update_prototype(role, feature)
            return detections

        non_ref = []
        for item in persons:
            i, feature, _ = item
            if self._looks_like_referee(feature):
                detections[i]["role"] = "referee"
            else:
                non_ref.append(item)

        if len(self._prototypes) < 2 and len(non_ref) >= 4:
            self._init_team_prototypes(non_ref)

        for i, feature, _ in non_ref:
            role = self._nearest_team(feature)
            detections[i]["role"] = role
            self._update_prototype(role, feature)

        return detections

    def color_for(self, role: str) -> tuple[int, int, int]:
        return self.ROLE_COLORS.get(role, self.ROLE_COLORS["unknown"])

    def _init_team_prototypes(self, items: list[tuple[int, np.ndarray, float]]):
        samples = np.float32([feature for _, feature, _ in items])
        if len(samples) < 2:
            return

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.01)
        _, labels, centers = cv2.kmeans(
            samples, 2, None, criteria, 5, cv2.KMEANS_PP_CENTERS
        )

        labels = labels.ravel()
        mean_x = []
        for cluster_id in (0, 1):
            xs = [items[j][2] for j, label in enumerate(labels) if label == cluster_id]
            mean_x.append(sum(xs) / len(xs) if xs else float("inf"))

        our_cluster = 0 if mean_x[0] <= mean_x[1] else 1
        opp_cluster = 1 - our_cluster
        self._prototypes["our_team"] = centers[our_cluster].copy()
        self._prototypes["opponent"] = centers[opp_cluster].copy()

    def _nearest_team(self, feature: np.ndarray) -> str:
        if len(self._prototypes) < 2:
            return "unknown"

        d_our = np.linalg.norm(feature - self._prototypes["our_team"])
        d_opp = np.linalg.norm(feature - self._prototypes["opponent"])
        return "our_team" if d_our <= d_opp else "opponent"

    def _nearest_manual_role(self, feature: np.ndarray) -> str:
        best_role = "unknown"
        best_dist = float("inf")
        for role, _ in ROLE_ORDER:
            dist = np.linalg.norm(feature - self._prototypes[role])
            if dist < best_dist:
                best_role = role
                best_dist = dist
        return best_role

    def _update_prototype(self, role: str, feature: np.ndarray):
        if role not in self._prototypes:
            return
        alpha = 0.01 if self._manual_roles else 0.04
        self._prototypes[role] = self._prototypes[role] * (1.0 - alpha) + feature * alpha

    @staticmethod
    def _looks_like_referee(feature: np.ndarray) -> bool:
        # feature = [cos(h), sin(h), saturation, value]
        sat = float(feature[2])
        val = float(feature[3])
        return val < 0.30 or (sat < 0.20 and val < 0.72)

    @staticmethod
    def _torso_feature(frame, bbox: list[int]) -> np.ndarray | None:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        bw = max(1, x2 - x1)
        bh = max(1, y2 - y1)

        tx1 = max(0, int(x1 + bw * 0.22))
        tx2 = min(w, int(x2 - bw * 0.22))
        ty1 = max(0, int(y1 + bh * 0.18))
        ty2 = min(h, int(y1 + bh * 0.58))
        if tx2 <= tx1 or ty2 <= ty1:
            return None

        crop = frame[ty1:ty2, tx1:tx2]
        if crop.size == 0:
            return None

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask = (hsv[:, :, 1] > 25) & (hsv[:, :, 2] > 25)
        if np.count_nonzero(mask) < 12:
            mean = hsv.reshape(-1, 3).mean(axis=0)
        else:
            mean = hsv[mask].mean(axis=0)

        hue = float(mean[0]) / 180.0 * 2.0 * np.pi
        sat = float(mean[1]) / 255.0
        val = float(mean[2]) / 255.0
        return np.array([np.cos(hue), np.sin(hue), sat, val], dtype=np.float32)


def pick_role_samples(frame, detections: list[dict]) -> TeamClassifier:
    """
    Let the user click one detected person for each role.
    Controls: left click selects the current role, Backspace undo, ESC/q cancel.
    """
    person_dets = [d for d in detections if d["class"] == "person"]
    if len(person_dets) < 3:
        raise RuntimeError("Need at least 3 person detections to sample team roles.")

    h, w = frame.shape[:2]
    scale = min(1280 / w, 720 / h, 1.0)
    view_w, view_h = int(w * scale), int(h * scale)
    base = cv2.resize(frame, (view_w, view_h))

    selected: dict[str, tuple[dict, np.ndarray]] = {}
    step = [0]

    def hit_test(x: int, y: int) -> dict | None:
        ox, oy = int(x / scale), int(y / scale)
        hits = []
        for det in person_dets:
            x1, y1, x2, y2 = det["bbox"]
            if x1 <= ox <= x2 and y1 <= oy <= y2:
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                dist = (cx - ox) ** 2 + (cy - oy) ** 2
                hits.append((dist, det))
        if not hits:
            return None
        return min(hits, key=lambda item: item[0])[1]

    def on_mouse(event, x, y, _flags, _param):
        if event != cv2.EVENT_LBUTTONDOWN or step[0] >= len(ROLE_ORDER):
            return

        det = hit_test(x, y)
        if det is None:
            return

        role, _ = ROLE_ORDER[step[0]]
        feature = TeamClassifier._torso_feature(frame, det["bbox"])
        if feature is None:
            return

        selected[role] = (det, feature)
        step[0] += 1

    cv2.namedWindow(PICK_WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(PICK_WINDOW, on_mouse)

    while step[0] < len(ROLE_ORDER):
        canvas = _render_role_picker(base, person_dets, selected, step[0], scale)
        cv2.imshow(PICK_WINDOW, canvas)

        key = cv2.waitKey(30) & 0xFF
        if key in (27, ord("q"), ord("Q")):
            cv2.destroyWindow(PICK_WINDOW)
            raise RuntimeError("Role sample picking cancelled.")
        if key in (8, 127) and step[0] > 0:
            step[0] -= 1
            role, _ = ROLE_ORDER[step[0]]
            selected.pop(role, None)

    cv2.destroyWindow(PICK_WINDOW)

    classifier = TeamClassifier()
    classifier.set_prototypes({role: feature for role, (_, feature) in selected.items()})
    return classifier


def _render_role_picker(
    base,
    person_dets: list[dict],
    selected: dict[str, tuple[dict, np.ndarray]],
    step: int,
    scale: float,
):
    canvas = base.copy()

    selected_ids = {id(det): role for role, (det, _) in selected.items()}
    for det in person_dets:
        x1, y1, x2, y2 = [int(v * scale) for v in det["bbox"]]
        role = selected_ids.get(id(det), "unknown")
        color = TeamClassifier.ROLE_COLORS.get(role, (180, 180, 180))
        thick = 3 if role != "unknown" else 1
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thick)
        if role != "unknown":
            cv2.putText(canvas, role, (x1, max(16, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 58), (0, 0, 0), -1)
    role, label = ROLE_ORDER[step]
    color = TeamClassifier.ROLE_COLORS[role]
    cv2.putText(canvas, f"Click sample: {label}", (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2)
    cv2.putText(canvas, "Backspace: undo | ESC/Q: cancel", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (230, 230, 230), 1)
    return canvas
