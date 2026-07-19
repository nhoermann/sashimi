from contextlib import contextmanager

from sashimi.hardware.optogenetics.interface import AbstractOptoInterface
from sashimi.waveforms import generate_stim_waveform


class MockOptoBoard(AbstractOptoInterface):
    def __init__(self, sample_rate, n_samples, conf):
        super().__init__(sample_rate, n_samples, conf)
        self._stim_parameters = None
        self._xy_galvo = (0.0, 0.0)
        self._gate = False
        self._running = False

    def set_stim_parameters(self, stim_parameters):
        self._stim_parameters = stim_parameters
        if self._running and stim_parameters.rois:
            xy, gate = generate_stim_waveform(
                stim_parameters.rois,
                self.sample_rate,
                self.n_samples,
                pattern=stim_parameters.pattern,
                spacing=stim_parameters.spacing,
                dwell_time=stim_parameters.dwell_time,
                transit_time=stim_parameters.transit_time,
                revolutions=stim_parameters.revolutions,
            )
            self._xy_galvo = (xy[0, -1], xy[1, -1])
            self._gate = bool(gate[-1])

    @property
    def xy_galvo(self):
        return self._xy_galvo

    @property
    def gate(self):
        return self._gate

    def start(self):
        self._running = True

    def stop(self):
        self._running = False
        self._xy_galvo = (0.0, 0.0)
        self._gate = False


@contextmanager
def open_mock_optoboard(sample_rate, n_samples, conf) -> MockOptoBoard:
    try:
        yield MockOptoBoard(sample_rate, n_samples, conf)
    finally:
        pass
