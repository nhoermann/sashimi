from sashimi.hardware.light_source.interface import AbstractLightSource


class MockLaser(AbstractLightSource):
    def __init__(self, port=None, intensity_units="mocks"):
        super().__init__(port, intensity_units)
        self._current = 0

    def set_power(self, current):
        """Sets power of laser based on self.intensity and self.intensity_units"""
        pass

    def close(self):
        pass

    @property
    def intensity(self):
        return self._current

    @intensity.setter
    def intensity(self, exp_val):
        self._current = exp_val

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, exp_val):
        self._status = exp_val
