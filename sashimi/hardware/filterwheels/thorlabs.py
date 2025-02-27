from warnings import warn
from sashimi.hardware.filterwheel.interface import AbstractFilterWheel, FilterWheelWarning
from sashimi.config import read_config

try:
    import pyvisa as visa

    manager = visa.ResourceManager()
except (ImportError, ValueError):
    warn("PyVisa not installed, no filterwheel control available", FilterWheelWarning)

conf = read_config()

class FW102C_FilterWheel(AbstractFilterWheel):
    def __init__(self, port):
        super().__init__(port)
        self.socket = manager.open_resource(
            self.port,
            **{
                "write_termination": "\r",
                "read_termination": "\r",
                "baud_rate": 115200,
                "parity": visa.constants.Parity.none,
                "stop_bits": visa.constants.StopBits.one,
                "encoding": "ascii",
            },
        )

    def set_filter(self, filter_id):
        try:
            if self._current > 0:
                self.socket.query("ci")
                self.socket.query("slc {:.1f}".format(self._current))
           
        except visa.VisaIOError:
            warn("Filter not set. Laser was unreachable", FilterWheelWarning)

    def close(self):
        self.socket.close()

    @property
    def filter(self):
        return self._filter

    @intensity.setter
    def intensity(self, exp_val):
        self._current = exp_val
        self.set_current()