from topview.homography import HomographyMapper


class CalibrationSet:
    """
    Collection of calibrated HomographyMapper instances at different frame positions.
    get_mapper(frame_idx) returns the calibration closest to the requested frame.
    """

    def __init__(self, calibrations: list[tuple]):
        if not calibrations:
            raise ValueError("At least one calibration is required.")
        self._items: list[tuple[int, HomographyMapper, object | None]] = sorted(
            [
                (item[0], item[1], item[2] if len(item) > 2 else None)
                for item in calibrations
            ],
            key=lambda x: x[0],
        )

    def get_mapper(self, frame_idx: int) -> HomographyMapper:
        return min(self._items, key=lambda x: abs(x[0] - frame_idx))[1]

    def get_exact(self, frame_idx: int) -> tuple[int, HomographyMapper] | None:
        for calibration_frame, mapper, _ in self._items:
            if calibration_frame == frame_idx:
                return calibration_frame, mapper
        return None

    def nearest_frame_index(self, frame_idx: int) -> int:
        return min(self._items, key=lambda x: abs(x[0] - frame_idx))[0]

    def add(self, frame_idx: int, mapper: HomographyMapper) -> None:
        self._items.append((frame_idx, mapper, None))
        self._items.sort(key=lambda x: x[0])

    @property
    def calibration_count(self) -> int:
        return len(self._items)
