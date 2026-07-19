from multiprocessing import Queue

import numpy as np

from sashimi.gui.optogenetics_gui import OptogeneticsSettingsWidget
from sashimi.state import OptoCalibration, OptogeneticsSettings, convert_stim_parameters


class FakeShapesLayer:
    def __init__(self):
        self.data = []
        self.visible = False
        self.mode = None


class FakePointsLayer:
    def __init__(self):
        self.data = []
        self.visible = False
        self.mode = None


class FakeWidDisplay:
    def __init__(self):
        self.opto_roi_layer = FakeShapesLayer()
        self.opto_calib_point_layer = FakePointsLayer()


class FakeOptogeneticsProcess:
    def __init__(self):
        self.parameter_queue = Queue()


class FakeStateWithOptogenetics:
    """Minimal stand-in for State exposing just what
    OptogeneticsSettingsWidget needs, so this test doesn't have to spin up
    the full hardware/process stack to check the ROI/calibration/stim
    control logic."""

    def __init__(self):
        self.conf = {
            "opto_board": {
                "voltage_limits": {
                    "x": {"min_val": -5, "max_val": 5},
                    "y": {"min_val": -5, "max_val": 5},
                }
            }
        }
        self.optogenetics = FakeOptogeneticsProcess()
        self.opto_calibration = OptoCalibration()
        self.optogenetics_settings = OptogeneticsSettings()

    def send_stim_parameters(self, pixel_rois):
        stim_parameters = convert_stim_parameters(
            self.optogenetics_settings, self.opto_calibration, pixel_rois
        )
        self.optogenetics.parameter_queue.put(stim_parameters)


def _calibrate_identity(state):
    """Register 3 calibration points for an identity (galvo == pixel)
    transform, so ROI conversion has something valid to work with."""
    for px, py in [(0, 0), (10, 0), (0, 10)]:
        state.opto_calibration.add_calibration_point(px, py, px, py)


def test_toggle_roi_drawing_shows_and_sets_add_mode(qtbot):
    state = FakeStateWithOptogenetics()
    wid_display = FakeWidDisplay()
    widget = OptogeneticsSettingsWidget(state, wid_display)
    qtbot.addWidget(widget)

    widget.btn_draw_rois.setChecked(True)
    widget.toggle_roi_drawing(True)
    assert wid_display.opto_roi_layer.visible is True

    widget.toggle_roi_drawing(False)
    assert wid_display.opto_roi_layer.visible is False


def test_clear_rois_empties_layer_data(qtbot):
    state = FakeStateWithOptogenetics()
    wid_display = FakeWidDisplay()
    widget = OptogeneticsSettingsWidget(state, wid_display)
    qtbot.addWidget(widget)

    wid_display.opto_roi_layer.data = [np.array([[0, 0], [1, 0], [1, 1]])]
    widget.clear_rois()
    assert wid_display.opto_roi_layer.data == []


def test_toggle_stimulation_with_no_rois_resets_button(qtbot):
    state = FakeStateWithOptogenetics()
    wid_display = FakeWidDisplay()
    widget = OptogeneticsSettingsWidget(state, wid_display)
    qtbot.addWidget(widget)

    widget.btn_stim.setChecked(True)
    widget.toggle_stimulation(True)
    assert widget.btn_stim.isChecked() is False


def test_toggle_stimulation_sends_converted_rois(qtbot):
    state = FakeStateWithOptogenetics()
    _calibrate_identity(state)
    wid_display = FakeWidDisplay()
    widget = OptogeneticsSettingsWidget(state, wid_display)
    qtbot.addWidget(widget)

    # napari shape data is (row, col) = (pixel_y, pixel_x):
    square_row_col = np.array([[0, 0], [0, 10], [10, 10], [10, 0]])
    wid_display.opto_roi_layer.data = [square_row_col]

    widget.toggle_stimulation(True)
    sent = state.optogenetics.parameter_queue.get(timeout=2)
    assert sent.rois, "expected at least one converted ROI to be queued"
    # Under the identity calibration, converted galvo coords should match
    # the (row, col) -> (x, y) flipped pixel coords exactly:
    np.testing.assert_allclose(sent.rois[0], square_row_col[:, ::-1], atol=1e-8)

    widget.toggle_stimulation(False)
    stopped = state.optogenetics.parameter_queue.get(timeout=2)
    assert stopped.rois == []


def test_add_and_remove_calibration_point(qtbot):
    state = FakeStateWithOptogenetics()
    wid_display = FakeWidDisplay()
    widget = OptogeneticsSettingsWidget(state, wid_display)
    qtbot.addWidget(widget)

    widget.manual_galvo_settings.galvo_x = 1.5
    widget.manual_galvo_settings.galvo_y = -2.0
    wid_display.opto_calib_point_layer.data = [(20, 10)]  # (row, col)

    widget.add_calibration_point()

    assert state.opto_calibration.calibration_points[-1] == (10, 20, 1.5, -2.0)

    widget.remove_calibration_point()
    assert len(state.opto_calibration.calibration_points) == 0


def test_add_calibration_point_consumes_the_marker(qtbot):
    # Regression check: add_calibration_point used to leave the just-added
    # marker sitting in calib_point_layer.data, so a second click without
    # drawing a new point would silently re-add it as a duplicate.
    state = FakeStateWithOptogenetics()
    wid_display = FakeWidDisplay()
    widget = OptogeneticsSettingsWidget(state, wid_display)
    qtbot.addWidget(widget)

    wid_display.opto_calib_point_layer.data = [(20, 10)]
    widget.add_calibration_point()
    assert len(wid_display.opto_calib_point_layer.data) == 0

    # A second click with no new point drawn must be a no-op, not a duplicate:
    widget.add_calibration_point()
    assert len(state.opto_calibration.calibration_points) == 1


def test_park_at_manual_position_sends_small_square_in_galvo_volts(qtbot):
    state = FakeStateWithOptogenetics()
    wid_display = FakeWidDisplay()
    widget = OptogeneticsSettingsWidget(state, wid_display)
    qtbot.addWidget(widget)

    widget.manual_galvo_settings.galvo_x = 2.0
    widget.manual_galvo_settings.galvo_y = -1.0
    widget.park_at_manual_position()

    sent = state.optogenetics.parameter_queue.get(timeout=2)
    assert len(sent.rois) == 1
    center = sent.rois[0].mean(axis=0)
    np.testing.assert_allclose(center, (2.0, -1.0), atol=1e-6)
