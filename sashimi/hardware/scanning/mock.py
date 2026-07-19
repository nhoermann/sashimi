from sashimi.hardware.scanning.__init__ import AbstractScanInterface
from sashimi.hardware.scanning.galvo import GalvoAxis
from contextlib import contextmanager
import numpy as np
from time import sleep


class MockBoard(AbstractScanInterface):
    def __init__(self, sample_rate, n_samples, conf):
        super().__init__(sample_rate, n_samples, conf)
        self.piezo_array = np.zeros(n_samples)

        # Same software safety limits as NIBoards, so mock-mode testing
        # exercises the identical validation path (see GalvoAxis).
        z_channel = conf["z_board"]["write"]["channel"]
        z_limits = conf["z_board"]["voltage_limits"]
        xy_channel = conf["xy_board"]["write"]["channel"]
        xy_limits = conf["xy_board"]["voltage_limits"]
        self._piezo_axis = GalvoAxis(z_channel, z_limits["piezo"], label="piezo")
        self._z_lateral_axis = GalvoAxis(
            z_channel, z_limits["lateral"], label="z_lateral"
        )
        self._z_frontal_axis = GalvoAxis(
            z_channel, z_limits["frontal"], label="z_frontal"
        )
        self._camera_trigger_axis = GalvoAxis(
            z_channel, z_limits["camera_trigger"], label="camera_trigger"
        )
        self._xy_lateral_axis = GalvoAxis(
            xy_channel, xy_limits["lateral"], label="xy_lateral"
        )
        self._xy_frontal_axis = GalvoAxis(
            xy_channel, xy_limits["frontal"], label="xy_frontal"
        )

    def start(self):
        pass

    def read(self):
        sleep(0.05)

    def write(self):
        sleep(0.05)

    @property
    def z_piezo(self):
        len_sampling = len(self.piezo_array)
        return np.ones(len_sampling)

    @z_piezo.setter
    def z_piezo(self, waveform):
        # Match NIBoards.z_piezo's own scaling, so the same voltage_limits
        # config validates against the same (volts) units in both boards.
        scaled = waveform * self.conf["piezo"]["scale"]
        self.piezo_array[:] = self._piezo_axis.validate(scaled)

    @property
    def z_frontal(self):
        return None

    @z_frontal.setter
    def z_frontal(self, waveform):
        self._z_frontal_axis.validate(waveform)

    @property
    def z_lateral(self):
        return None

    @z_lateral.setter
    def z_lateral(self, waveform):
        self._z_lateral_axis.validate(waveform)

    @property
    def camera_trigger(self):
        return None

    @camera_trigger.setter
    def camera_trigger(self, waveform):
        self._camera_trigger_axis.validate(waveform)

    @property
    def xy_frontal(self):
        return None

    @xy_frontal.setter
    def xy_frontal(self, waveform):
        self._xy_frontal_axis.validate(waveform)

    @property
    def xy_lateral(self):
        return None

    @xy_lateral.setter
    def xy_lateral(self, waveform):
        self._xy_lateral_axis.validate(waveform)


@contextmanager
def open_mockboard(sample_rate, n_samples, conf) -> MockBoard:
    try:
        yield MockBoard(sample_rate, n_samples, conf)
    finally:
        pass
