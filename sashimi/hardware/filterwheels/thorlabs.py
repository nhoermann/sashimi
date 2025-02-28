from warnings import warn
from sashimi.hardware.filterwheels.interface import AbstractFilterWheel, FilterWheelWarning
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
        self._filter = conf["filterwheel"]["default_filter"]
        self.filter_options = conf["filterwheel"]["filter_options"]
        self.set_filter(self._filter)
    
    def set_filter(self, new_filter):
        # Convert new_filter string into id:
        new_filter_id = self.filter_options.index(new_filter)+1
        # Filters are not zero indexed, first entry is 1, second is position 2 etc.
        try:
            self.socket.query("pos={}".format(new_filter_id))
           
        except visa.VisaIOError:
            warn("Filter not set. Filterwheel was unreachable", FilterWheelWarning)

    def close(self):
        self.socket.close()

    @property
    def filter(self):
        return self._filter

    @filter.setter
    def filter(self, new_filter):
        self._filter = new_filter
        self.set_filter(new_filter)
        #print("Filter set to: ", str(self._filter))