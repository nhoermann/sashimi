from enum import Enum
from abc import ABC, abstractmethod

class ShutterState(Enum):
    ON = 1
    OFF = 2

class ShutterException(Exception):
    pass

class ShutterWarning(Warning):
    pass

class AbstractShutter(ABC):
    def __init__(self, port):
        self.port = port
        self._status = ShutterState.OFF

    @abstractmethod
    def set_shutter(self, command):
        """Sets power of laser based on self.intensity and self.intensity_units"""
        pass

    @abstractmethod
    def close(self):
        pass

    @property
    @abstractmethod
    def status(self):
        return self._status

    @status.setter
    @abstractmethod
    def status(self, val):
        pass
