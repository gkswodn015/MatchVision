import os
import json
from collections import Counter, defaultdict

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
        self.team_ids_path = os.path.join(self.result_dir, f"{video_name}_team_ids.json")
        self.team_id_votes = defaultdict(Counter)

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

            tracks, positions = self._apply_roster_constraints(tracks, positions)
            self._record_team_ids(tracks)

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
            "team_ids_path": self.team_ids_path,
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

    def _apply_roster_constraints(
        self,
        tracks: list[dict],
        positions: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        pos_map = {p["id"]: p for p in positions}
        ball_tracks = [t for t in tracks if t.get("class") == "sports ball"]
        person_tracks = [
            t for t in tracks
            if t.get("class") == "person" and t["id"] in pos_map
        ]

        person_tracks = sorted(
            person_tracks,
            key=lambda t: (
                bool(t.get("predicted", False)),
                int(t.get("lost", 0)),
                -int(t.get("hits", 0)),
            ),
        )[:25]

        self._assign_goalkeepers(person_tracks, pos_map)
        self._limit_referee_count(person_tracks, pos_map)
        self._balance_team_counts(person_tracks)
        person_tracks = self._visible_person_tracks(person_tracks)

        kept_ids = {t["id"] for t in person_tracks + ball_tracks}
        filtered_positions = [p for p in positions if p["id"] in kept_ids]
        return person_tracks + ball_tracks, filtered_positions

    @staticmethod
    def _visible_person_tracks(person_tracks: list[dict]) -> list[dict]:
        return [
            track for track in person_tracks
            if track.get("role") in {"our_team", "opponent", "referee"}
        ]

    def _assign_goalkeepers(self, person_tracks: list[dict], pos_map: dict[int, dict]) -> None:
        left_keeper = self._select_goalkeeper(person_tracks, pos_map, side="left")
        right_keeper = self._select_goalkeeper(
            person_tracks,
            pos_map,
            side="right",
            exclude_id=left_keeper["id"] if left_keeper else None,
        )

        if left_keeper is not None:
            left_keeper["goalkeeper_candidate"] = "left"
        if right_keeper is not None:
            right_keeper["goalkeeper_candidate"] = "right"

    def _select_goalkeeper(
        self,
        person_tracks: list[dict],
        pos_map: dict[int, dict],
        side: str,
        exclude_id: int | None = None,
    ) -> dict | None:
        goal_x = 0.0 if side == "left" else FIELD_W
        penalty_min_x, penalty_max_x = (
            (0.0, 16.5) if side == "left" else (88.5, FIELD_W)
        )

        candidates = [
            t for t in person_tracks
            if t["id"] != exclude_id
            and t["id"] in pos_map
            and self._inside_penalty_box(pos_map[t["id"]], penalty_min_x, penalty_max_x)
        ]
        if not candidates:
            return None

        return min(
            candidates,
            key=lambda t: (
                self._goal_distance(pos_map[t["id"]], goal_x),
                int(t.get("lost", 0)),
                -int(t.get("hits", 0)),
            ),
        )

    @staticmethod
    def _inside_penalty_box(pos: dict, min_x: float, max_x: float) -> bool:
        return min_x <= pos["mx"] <= max_x and 13.84 <= pos["my"] <= 54.16

    @staticmethod
    def _goal_distance(pos: dict, goal_x: float) -> float:
        return ((pos["mx"] - goal_x) ** 2 + (pos["my"] - 34.0) ** 2) ** 0.5

    def _limit_referee_count(self, person_tracks: list[dict], pos_map: dict[int, dict]) -> None:
        referees = [t for t in person_tracks if t.get("role") == "referee"]
        if len(referees) <= 1:
            return

        main_ref = max(
            referees,
            key=lambda t: (
                not self._near_field_boundary(pos_map.get(t["id"])),
                self._role_vote(t, "referee"),
                int(t.get("hits", 0)),
                -int(t.get("lost", 0)),
            ),
        )

        allowed_refs = {main_ref["id"]}
        boundary_refs = [
            t for t in referees
            if t["id"] != main_ref["id"] and self._near_field_boundary(pos_map.get(t["id"]))
        ]
        boundary_refs = sorted(
            boundary_refs,
            key=lambda t: (
                self._role_vote(t, "referee"),
                int(t.get("hits", 0)),
                -int(t.get("lost", 0)),
            ),
            reverse=True,
        )[:2]
        allowed_refs.update(t["id"] for t in boundary_refs)

        for track in referees:
            if track["id"] in allowed_refs:
                continue
            if track.get("locked_role") == "referee":
                continue
            track["role"] = self._best_team_role(track)

    def _balance_team_counts(self, person_tracks: list[dict]) -> None:
        for role in ("our_team", "opponent"):
            team = [t for t in person_tracks if t.get("role") == role]
            if len(team) <= 10:
                continue

            other = "opponent" if role == "our_team" else "our_team"
            other_count = sum(1 for t in person_tracks if t.get("role") == other)
            overflow = sorted(
                team,
                key=lambda t: (
                    self._role_vote(t, role),
                    int(t.get("hits", 0)),
                    -int(t.get("lost", 0)),
                ),
            )[:len(team) - 10]

            for track in overflow:
                if track.get("locked_role") == role:
                    continue
                if other_count < 10:
                    track["role"] = other
                    other_count += 1
                else:
                    track["role"] = "unknown"

    @staticmethod
    def _role_vote(track: dict, role: str) -> int:
        return int(track.get("role_votes", {}).get(role, 0))

    def _best_team_role(self, track: dict) -> str:
        our_votes = self._role_vote(track, "our_team")
        opponent_votes = self._role_vote(track, "opponent")
        if our_votes > opponent_votes:
            return "our_team"
        if opponent_votes > our_votes:
            return "opponent"
        return "our_team"

    @staticmethod
    def _near_field_boundary(pos: dict | None, margin: float = 3.0) -> bool:
        if pos is None:
            return False
        return (
            pos["mx"] <= margin
            or pos["mx"] >= FIELD_W - margin
            or pos["my"] <= margin
            or pos["my"] >= FIELD_H - margin
        )

    def _cleanup(self):
        self.cap.release()
        self.detected_writer.release()
        self.topview_writer.release()
        if self.display:
            cv2.destroyAllWindows()

        self._write_team_ids()

        print(f"\nSaved detected video: {self.detected_path}")
        print(f"Saved topview video:  {self.topview_path}")
        print(f"Saved team IDs:       {self.team_ids_path}")

        ratios = self.possession._ratios()
        if ratios:
            print("\n=== Possession ===")
            for tid, ratio in sorted(ratios.items(), key=lambda x: -x[1]):
                print(f"  ID {tid:3d}: {ratio*100:.1f}%")

    def _record_team_ids(self, tracks: list[dict]) -> None:
        for track in tracks:
            if track.get("class") != "person" or track.get("predicted"):
                continue

            role = self._team_role_for_summary(track)
            if role in ("home", "away", "referee"):
                self.team_id_votes[int(track["id"])][role] += 1

    def _team_role_for_summary(self, track: dict) -> str:
        role = track.get("role", "unknown")
        if role == "our_team":
            return "home"
        if role == "opponent":
            return "away"
        if role == "referee":
            return "referee"
        if role in ("goalkeeper_left", "goalkeeper_right"):
            return self._goalkeeper_team_role(track)
        return "unknown"

    def _goalkeeper_team_role(self, track: dict) -> str:
        votes = track.get("role_votes", {})
        home_votes = int(votes.get("our_team", 0))
        away_votes = int(votes.get("opponent", 0))
        if home_votes == 0 and away_votes == 0:
            return "unknown"
        return "home" if home_votes >= away_votes else "away"

    def _write_team_ids(self) -> None:
        groups = {
            "home_ids": [],
            "away_ids": [],
            "referee_ids": [],
            "unknown_ids": [],
        }

        for track_id, votes in sorted(self.team_id_votes.items()):
            if not votes:
                continue
            role, frames = votes.most_common(1)[0]
            item = {"id": track_id, "frames": frames}
            if role == "home":
                groups["home_ids"].append(item)
            elif role == "away":
                groups["away_ids"].append(item)
            elif role == "referee":
                groups["referee_ids"].append(item)
            else:
                groups["unknown_ids"].append(item)

        with open(self.team_ids_path, "w", encoding="utf-8") as fp:
            json.dump(groups, fp, ensure_ascii=False, indent=2)
