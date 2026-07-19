from enum import Enum
from abc import ABC, abstractmethod
from typing import Optional


class LaserState(Enum):
    ON = 1
    OFF = 2


class LaserException(Exception):
    pass


class LaserWarning(Warning):
    pass


class AbstractLightSource(ABC):
    def __init__(self, port, intensity_units=None):
        self.port = port
        self._status = LaserState.OFF
        self.intensity_units = intensity_units

    def start(self):
        pass

    @abstractmethod
    def set_power(self, current):
        """Sets power of laser based on self.intensity and self.intensity_units"""
        pass

    @abstractmethod
    def close(self):
        pass

    @property
    @abstractmethod
    def intensity(self):
        return None

    @intensity.setter
    @abstractmethod
    def intensity(self, exp_val):
        pass

    @property
    @abstractmethod
    def status(self):
        return self._status

    @status.setter
    @abstractmethod
    def status(self, exp_val):
        pass

    @property
    def channels(self):
        """List of independently controllable AbstractLightSource objects
        exposed by this unit. Defaults to a single-channel unit (itself);
        override for multi-channel combiners like Toptica CLE/MLE, where one
        physical connection exposes several independently settable channels.
        """
        return [self]

    @property
    def label(self):
        """Human/GUI-facing label identifying this channel."""
        return self.port

    @classmethod
    def probe(cls, port) -> Optional[dict]:
        """Attempt to identify whether this driver's hardware is present at
        `port`. Return a dict describing what was found on success (at least
        a "name" key matching this driver's light_source_class_dict entry),
        or None if this driver doesn't recognize what's connected there.

        Used by sashimi.hardware.light_source.detect.probe_light_sources for
        auto-detection. Opening/closing the port briefly to check for a
        response is this method's own responsibility; the default here does
        not attempt any probing.
        """
        return None
