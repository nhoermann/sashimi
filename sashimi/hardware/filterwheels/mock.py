from sashimi.hardware.filterwheels.interface import AbstractFilterWheel


class MockFilterWheel(AbstractFilterWheel):
    def __init__(self, port=None):
        super().__init__(port)
        self.port = port
        #self._current = 0
        #self.intensity_units = "mocks"

    def set_filter(self, filter):
        """Sets filter"""
        # Check if filter is in Filter
        pass

    def close(self):
        pass

    @property
    def filter(self):
        return self._filter

    @filter.setter
    def filter(self, desired_filter):
        self._filter = desired_filter
        print("Filter set to: ", str(self._filter))

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, exp_val):
        self._status = exp_val
       
