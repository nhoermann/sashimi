import numpy as np
import pytest

from sashimi.hardware.optogenetics.interface import OptoWarning, StimParameters
from sashimi.hardware.optogenetics.mock import MockOptoBoard
from sashimi.hardware.optogenetics.ni import OptoNIBoard

SAMPLE_RATE = 40000
N_SAMPLES = 4000
CONF = {}  # MockOptoBoard doesn't read anything from conf

OPTO_NI_CONF = {
    "opto_board": {
        "write": {
            "x_channel": "Dev3/ao0",
            "y_channel": "Dev3/ao1",
            "gate_channel": "Dev3/port0/line0",
        },
        "voltage_limits": {
            "x": {"min_val": -5, "max_val": 5},
            "y": {"min_val": -5, "max_val": 5},
        },
    }
}


def test_stim_parameters_defaults_are_not_shared():
    # Regression check for the dataclass mutable-default pitfall already hit
    # once in sashimi/hardware/scanning/scanloops.py (Python 3.11+ forbids
    # exactly this for nested dataclass instances, but a plain list default
    # without field(default_factory=list) would silently share state across
    # instances instead of raising - checking behavior directly here).
    a = StimParameters()
    b = StimParameters()
    a.rois.append("roi")
    assert b.rois == []


def test_mock_opto_board_idle_before_start():
    board = MockOptoBoard(SAMPLE_RATE, N_SAMPLES, CONF)
    square = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    board.set_stim_parameters(StimParameters(rois=[square]))
    # Not started yet - shouldn't compute/move to a waveform position:
    assert board.xy_galvo == (0.0, 0.0)
    assert board.gate is False


def test_mock_opto_board_computes_waveform_once_started():
    board = MockOptoBoard(SAMPLE_RATE, N_SAMPLES, CONF)
    square = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    board.start()
    board.set_stim_parameters(StimParameters(rois=[square], dwell_time=0.01))
    # Some position should now be set (last sample of the generated waveform):
    assert board.xy_galvo != (0.0, 0.0) or board.gate

    board.stop()
    assert board.xy_galvo == (0.0, 0.0)
    assert board.gate is False


def test_mock_opto_board_empty_rois_does_not_crash():
    board = MockOptoBoard(SAMPLE_RATE, N_SAMPLES, CONF)
    board.start()
    board.set_stim_parameters(StimParameters(rois=[]))
    assert board.xy_galvo == (0.0, 0.0)
    assert board.gate is False


def test_opto_niboard_safe_buffer_falls_back_to_laser_off_on_bad_params():
    # Regression check: _generate_buffer can raise ValueError (out-of-range
    # calibration point, or an ROI too small for the raster spacing) - this
    # used to be called unguarded from the background writer thread, killing
    # it silently and leaving the laser gate stuck at its last value.
    # _safe_buffer must instead warn and fall back to an all-off buffer.
    board = OptoNIBoard(SAMPLE_RATE, N_SAMPLES, OPTO_NI_CONF)
    out_of_range_square = np.array([[0, 0], [100, 0], [100, 100], [0, 100]])
    board.set_stim_parameters(
        StimParameters(rois=[out_of_range_square], dwell_time=0.01)
    )

    with pytest.warns(OptoWarning):
        xy, gate = board._safe_buffer()

    assert not gate.any()
    assert np.all(xy == 0)
