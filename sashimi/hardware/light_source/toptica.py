from warnings import warn
from sashimi.hardware.light_source.interface import (
    AbstractLightSource,
    LaserState,
    LaserException,
    LaserWarning,
)

try:
    import pyvisa as visa

    manager = visa.ResourceManager()
except (ImportError, ValueError):
    warn("PyVisa not installed, no laser control available", LaserWarning)


# Command strings below follow Toptica's documented ASCII serial command
# convention for CLE (Combiner Laser Engine) and MLE (Multi Laser Engine)
# units: `<command> <value>` to set, `<command>?` to query, one line per
# command/reply. These are written from general knowledge of that
# convention, not a specific firmware manual - verify the exact command
# strings against your unit's "Serial Command Set Reference" before relying
# on this against real hardware.
_POWER_SET = "la{ch} pow {value:.1f}"
_POWER_QUERY = "la{ch} pow?"
_LASER_ON = "la{ch} on"
_LASER_OFF = "la{ch} off"
_IDENTITY_QUERY = "identify?"


class TopticaChannel(AbstractLightSource):
    """A single laser channel inside a Toptica CLE/MLE combiner unit.

    Channels share the unit's one serial connection (`unit.socket`) rather
    than owning their own - only the owning `_TopticaCombinerUnit` opens and
    closes the port.
    """

    def __init__(self, unit, channel_index):
        super().__init__(unit.port, unit.intensity_units)
        self.unit = unit
        self.channel_index = channel_index
        self._current = 0

    @property
    def label(self):
        return f"{self.unit.port}-ch{self.channel_index}"

    def set_power(self, current):
        """Sets power of laser based on self.intensity and self.intensity_units"""
        pass

    def close(self):
        # Channels don't own the connection - the parent unit closes it.
        pass

    @property
    def intensity(self):
        return self._current

    @intensity.setter
    def intensity(self, exp_val):
        self._current = exp_val
        try:
            self.unit.socket.query(
                _POWER_SET.format(ch=self.channel_index, value=exp_val)
            )
        except visa.VisaIOError:
            warn("Current not set. Laser was unreachable", LaserWarning)

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, exp_val):
        self._status = exp_val
        command = (
            _LASER_ON.format(ch=self.channel_index)
            if exp_val == LaserState.ON
            else _LASER_OFF.format(ch=self.channel_index)
        )
        try:
            self.unit.socket.query(command)
        except visa.VisaIOError:
            warn("Status not set. Laser was unreachable", LaserWarning)


class _TopticaCombinerUnit(AbstractLightSource):
    """Shared base for Toptica CLE (Combiner Laser Engine) and MLE (Multi
    Laser Engine) units: a single serial/USB connection exposing several
    independently-controllable laser diode channels, unlike Cobolt's
    one-connection-one-laser model.
    """

    #: Substring expected in the unit's identify? reply; set by subclasses.
    IDENTITY_MATCH = ""

    #: Ceiling on how many channel indices to probe when the unit doesn't
    #: report its channel count directly (see detect_channels()).
    MAX_CHANNELS_TO_PROBE = 6

    _VISA_KWARGS = {
        "write_termination": "\r\n",
        "read_termination": "\r\n",
        "baud_rate": 115200,
        "encoding": "ascii",
    }

    def __init__(self, port, intensity_units=None, n_channels=None):
        super().__init__(port, intensity_units)
        self.socket = manager.open_resource(self.port, **self._VISA_KWARGS)
        self._channels = [
            TopticaChannel(self, i + 1)
            for i in range(
                n_channels if n_channels is not None else self.detect_channels()
            )
        ]

    def detect_channels(self):
        """Probe channel indices 1..MAX_CHANNELS_TO_PROBE, stopping at the
        first one that doesn't respond, to find how many laser channels this
        unit actually has configured.
        """
        count = 0
        for i in range(1, self.MAX_CHANNELS_TO_PROBE + 1):
            try:
                self.socket.query(_POWER_QUERY.format(ch=i))
                count += 1
            except visa.VisaIOError:
                break
        return max(count, 1)

    @property
    def channels(self):
        return self._channels

    def set_power(self, current):
        """Sets power of laser based on self.intensity and self.intensity_units"""
        pass

    def close(self):
        self.socket.close()

    @property
    def intensity(self):
        return None

    @intensity.setter
    def intensity(self, exp_val):
        raise LaserException(
            "Set intensity on individual channels (unit.channels), not the unit itself."
        )

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, exp_val):
        self._status = exp_val

    @classmethod
    def probe(cls, port):
        """Briefly open `port` and check whether a Toptica unit matching this
        class (CLE vs MLE, distinguished by IDENTITY_MATCH) answers there.
        """
        try:
            resource = manager.open_resource(
                port, **{**cls._VISA_KWARGS, "timeout": 500}
            )
            try:
                identity = resource.query(_IDENTITY_QUERY)
            finally:
                resource.close()
        except Exception:
            return None
        if cls.IDENTITY_MATCH not in identity:
            return None
        return {"identity": identity}


class TopticaCLE(_TopticaCombinerUnit):
    """Toptica CLE (Combiner Laser Engine)."""

    IDENTITY_MATCH = "CLE"


class TopticaMLE(_TopticaCombinerUnit):
    """Toptica MLE (Multi Laser Engine)."""

    IDENTITY_MATCH = "MLE"
