from sashimi.hardware.filterwheels.interface import AbstractFilterWheel


class MockFilterWheel(AbstractFilterWheel):
    def __init__(self, port=None):
        super().__init__(port)
        self.port = port
        
    def set_filter(self, filter):
        """Sets filter"""
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

