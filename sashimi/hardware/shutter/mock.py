from sashimi.hardware.shutter.interface import AbstractShutter

class MockShutter(AbstractShutter):
    def __init__(self, port=None):
        super().__init__(port)

    def set_shutter(self, command):
        """Sets shutter"""
        pass

    def close(self):
        pass

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, command):
        self._status = command
        # print("Shutter set to: ", str(self._status))