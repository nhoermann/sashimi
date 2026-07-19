"""Trimmed port of dirigo's validated-physical-quantity pattern
(dirigo/components/units.py) - keeping only what sashimi's galvo hardening
needs: Angle, Voltage, Frequency, SampleRate and their ranges. Dirigo's
cross-quantity unit algebra (e.g. Position / Time -> Velocity, via a global
dimension registry) is dropped - sashimi only needs same-unit arithmetic and
range validation.
"""

import math
import re
from typing import Dict, Generic, TypeVar

T_UQ = TypeVar("T_UQ", bound="UnitQuantity")

_NUMERIC = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_UNIT_TOKEN = r"[A-Za-zμµΩ/]+"
_VALUE_WITH_UNIT = re.compile(rf"^\s*({_NUMERIC})\s*({_UNIT_TOKEN})\s*$")


class UnitQuantity(float):
    """A float tagged with its unit, parsed from strings like "10 deg" or
    "5 V" and always stored internally in the class's base unit.
    """

    unit: str
    __slots__ = ("unit",)

    #: Maps allowed unit strings to their multiplier into the base unit;
    #: override in subclasses. The first entry is treated as the base unit.
    ALLOWED_UNITS_AND_MULTIPLIERS: Dict[str, float] = {"": 1.0}

    def __new__(cls, quantity):
        if isinstance(quantity, str):
            value, unit = cls._parse(quantity)
            if unit not in cls.ALLOWED_UNITS_AND_MULTIPLIERS:
                raise ValueError(
                    f"Invalid unit {unit!r} for {cls.__name__}. "
                    f"Allowed units: {list(cls.ALLOWED_UNITS_AND_MULTIPLIERS)}."
                )
            base_value = value * cls.ALLOWED_UNITS_AND_MULTIPLIERS[unit]
        elif isinstance(quantity, (int, float)):
            base_value = float(quantity)
        else:
            raise TypeError(
                "Input must be a string with units (e.g. '5 V') or a float "
                "in the base unit."
            )
        instance = super().__new__(cls, base_value)
        instance.unit = next(iter(cls.ALLOWED_UNITS_AND_MULTIPLIERS))
        return instance

    @staticmethod
    def _parse(quantity: str):
        match = _VALUE_WITH_UNIT.match(quantity)
        if not match:
            raise ValueError(f"Invalid format for value with unit: {quantity!r}.")
        value_str, unit = match.groups()
        return float(value_str), unit

    def __repr__(self):
        return f"{float(self):.6g} {self.unit}"

    def __neg__(self):
        return type(self)(-float(self))

    def __add__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return type(self)(float(self) + float(other))

    def __sub__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return type(self)(float(self) - float(other))

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return type(self)(float(self) * other)
        return NotImplemented

    __rmul__ = __mul__

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return type(self)(float(self) / other)
        if isinstance(other, type(self)):
            return float(self) / float(other)
        return NotImplemented


class Angle(UnitQuantity):
    """Angular value, base unit radians."""

    ALLOWED_UNITS_AND_MULTIPLIERS = {
        "rad": 1.0,
        "mrad": 1e-3,
        "deg": math.pi / 180,
    }


class Voltage(UnitQuantity):
    """Voltage value, base unit volts."""

    ALLOWED_UNITS_AND_MULTIPLIERS = {
        "V": 1.0,
        "mV": 1e-3,
        "kV": 1e3,
    }


class Frequency(UnitQuantity):
    """Frequency value, base unit hertz."""

    ALLOWED_UNITS_AND_MULTIPLIERS = {
        "Hz": 1.0,
        "kHz": 1e3,
        "MHz": 1e6,
        "GHz": 1e9,
    }


class SampleRate(Frequency):
    """Samples-per-second rate; dimensionally a Frequency, with its own unit
    labels (relevant e.g. for a DAQ sample clock rate).
    """

    ALLOWED_UNITS_AND_MULTIPLIERS = {
        "S/s": 1.0,
        "kS/s": 1e3,
        "MS/s": 1e6,
        "GS/s": 1e9,
    }


class RangeWithUnits(Generic[T_UQ]):
    """A validated [min, max] range of some UnitQuantity subclass."""

    #: Concrete UnitQuantity subclass this range holds; set in subclasses.
    UNIT_QUANTITY_CLASS: type

    def __init__(self, min, max):  # noqa: A002 (shadows builtin, matches dirigo)
        self._min = self.UNIT_QUANTITY_CLASS(min)
        self._max = self.UNIT_QUANTITY_CLASS(max)
        if float(self._min) >= float(self._max):
            raise ValueError(
                f"Invalid range: min ({self._min}) must be less than max ({self._max})."
            )

    @property
    def min(self) -> T_UQ:
        return self._min

    @property
    def max(self) -> T_UQ:
        return self._max

    @property
    def range(self) -> T_UQ:
        return self.UNIT_QUANTITY_CLASS(float(self._max) - float(self._min))

    def within_range(self, value) -> bool:
        return float(self._min) <= float(value) <= float(self._max)

    def __repr__(self):
        return f"{type(self).__name__}({self._min!r}, {self._max!r})"


class AngleRange(RangeWithUnits[Angle]):
    UNIT_QUANTITY_CLASS = Angle

    @property
    def min_degrees(self) -> float:
        return float(self.min) * 180 / math.pi

    @property
    def max_degrees(self) -> float:
        return float(self.max) * 180 / math.pi


class VoltageRange(RangeWithUnits[Voltage]):
    UNIT_QUANTITY_CLASS = Voltage
