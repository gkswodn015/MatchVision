import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detector.classifier import TeamClassifier


def test_manual_prototypes_do_not_drift():
    classifier = TeamClassifier()
    original = np.array([1.0, 0.0, 0.8, 0.8], dtype=np.float32)
    classifier.set_prototypes({
        "our_team": original,
        "opponent": np.array([-1.0, 0.0, 0.8, 0.8], dtype=np.float32),
        "referee": np.array([0.0, 1.0, 0.2, 0.2], dtype=np.float32),
    })

    classifier._update_prototype(
        "our_team",
        np.array([-1.0, 0.0, 0.1, 0.1], dtype=np.float32),
    )

    np.testing.assert_allclose(classifier._prototypes["our_team"], original)
