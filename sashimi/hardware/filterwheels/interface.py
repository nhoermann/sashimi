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
    def filter(self):
        pass

    @filter.setter
    def filter(self, desired_filter):
        pass
        
