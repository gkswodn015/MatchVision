import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from topview.calibration_set import CalibrationSet
from topview.homography import HomographyMapper


def _mapper() -> HomographyMapper:
    return HomographyMapper(
        [[0, 0], [100, 0], [100, 100], [0, 100]],
        [[0, 0], [10, 0], [10, 10], [0, 10]],
    )


def test_calibration_set_finds_exact_frame():
    mapper = _mapper()
    calib = CalibrationSet([(25, mapper, np.zeros((10, 10, 3), dtype=np.uint8))])

    assert calib.get_exact(25)[1] is mapper
    assert calib.get_exact(26) is None


def test_homography_clone_does_not_mutate_original():
    mapper = _mapper()
    clone = mapper.clone()
    clone.update_H(np.eye(3, dtype=np.float32))

    assert not np.allclose(mapper.H, clone.H)
