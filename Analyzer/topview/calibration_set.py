from topview.homography import HomographyMapper


class CalibrationSet:
    """
    여러 프레임 위치에서 보정된 HomographyMapper 컬렉션.
    get_mapper(frame_idx) 는 프레임 번호 기준 가장 가까운 보정값을 반환한다.
    """

    def __init__(self, calibrations: list[tuple[int, HomographyMapper]]):
        if not calibrations:
            raise ValueError("캘리브레이션이 하나 이상 필요합니다.")
        self._items: list[tuple[int, HomographyMapper]] = sorted(
            calibrations, key=lambda x: x[0]
        )

    def get_mapper(self, frame_idx: int) -> HomographyMapper:
        return min(self._items, key=lambda x: abs(x[0] - frame_idx))[1]

    def add(self, frame_idx: int, mapper: HomographyMapper) -> None:
        self._items.append((frame_idx, mapper))
        self._items.sort(key=lambda x: x[0])

    @property
    def calibration_count(self) -> int:
        return len(self._items)
