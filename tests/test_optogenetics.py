import numpy as np

from sashimi.hardware.optogenetics.interface import StimParameters
from sashimi.hardware.optogenetics.mock import MockOptoBoard

SAMPLE_RATE = 40000
N_SAMPLES = 4000
CONF = {}  # MockOptoBoard doesn't read anything from conf


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
