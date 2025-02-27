from enum import Enum
from abc import ABC, abstractmethod

class FilterWheelException(Exception):
    pass

class FilterWheelWarning(Warning):
    pass

class AbstractFilterWheel(ABC):
    def __init__(self, port):
        self.port = port
        
    @abstractmethod
    def set_filter(self, command):
        """Sets filter"""
        pass

    @abstractmethod
    def close(self):
        pass

    @property
    @abstractmethod
    def status(self):
        pass

    @status.setter
    @abstractmethod
    def status(self, val):
        pass
