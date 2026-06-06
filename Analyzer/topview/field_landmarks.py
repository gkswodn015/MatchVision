# FIFA standard pitch: 105m x 68m
# Origin (0, 0) = top-left corner, x-axis = right, y-axis = down
FIELD_W = 105.0
FIELD_H = 68.0

LANDMARKS: dict[str, tuple[float, float]] = {
    "Top-left corner": (0.0, 0.0),
    "Top-right corner": (105.0, 0.0),
    "Bottom-right corner": (105.0, 68.0),
    "Bottom-left corner": (0.0, 68.0),

    "Halfway line top": (52.5, 0.0),
    "Halfway line bottom": (52.5, 68.0),
    "Center spot": (52.5, 34.0),

    "Left penalty box upper-right": (16.5, 13.84),
    "Left penalty box lower-right": (16.5, 54.16),
    "Left penalty box upper-left": (0.0, 13.84),
    "Left penalty box lower-left": (0.0, 54.16),

    "Right penalty box upper-left": (88.5, 13.84),
    "Right penalty box lower-left": (88.5, 54.16),
    "Right penalty box upper-right": (105.0, 13.84),
    "Right penalty box lower-right": (105.0, 54.16),

    "Left goal area upper-right": (5.5, 24.84),
    "Left goal area lower-right": (5.5, 43.16),
    "Right goal area upper-left": (99.5, 24.84),
    "Right goal area lower-left": (99.5, 43.16),

    "Left penalty spot": (11.0, 34.0),
    "Right penalty spot": (94.0, 34.0),

    "Left goalpost upper": (0.0, 30.34),
    "Left goalpost lower": (0.0, 37.66),
    "Right goalpost upper": (105.0, 30.34),
    "Right goalpost lower": (105.0, 37.66),
}
