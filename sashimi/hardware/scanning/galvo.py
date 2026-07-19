"""Validated galvo-axis write boundary, adapted from dirigo's GalvoScanner
(dirigo/hw_interfaces/scanner.py) and its NI-DAQ channel-name sanity check
(dirigo/plugins/scanners.py's validate_ni_channel).

Trimmed to what sashimi's galvo channels need: reject an out-of-range value
before it's written to hardware, rather than dirigo's full amplitude/
frequency/waveform-type scan generator - sashimi generates its own waveforms
in sashimi/waveforms.py and just needs a safety-checked write boundary
underneath the existing per-sample piezo->galvo sync (calc_sync in
scanloops.py), not a replacement for it.
"""

import numpy as np

from sashimi.hardware.scanning.units import Voltage, VoltageRange


def validate_ni_channel(channel_name: str) -> str:
    """Sanity-check an NI-DAQ channel/terminal name's format at config-load
    time (adapted from dirigo's validate_ni_channel). This only catches
    obviously malformed strings early; it does not check the name against a
    live device; the write task itself already validates that.
    """
    if "/" not in channel_name or channel_name.count("/") > 3:
        raise ValueError(
            f"Invalid channel name format, {channel_name!r}. Valid formats: "
            f"'[device]/[channel]' or '/[device]/[terminal]'. "
            f"Examples: 'Dev1/ao0', '/Dev1/PFI4'."
        )
    return channel_name


class GalvoAxis:
    """Validates values (in volts) against a configured safe range before
    they are written to a galvo mirror's analog output channel.
    """

    def __init__(self, channel: str, voltage_limits: dict, label: str = ""):
        self.channel = validate_ni_channel(channel)
        self.label = label or channel
        self.voltage_range = VoltageRange(
            voltage_limits["min_val"], voltage_limits["max_val"]
        )

    def validate(self, values) -> np.ndarray:
        """Check that every sample in `values` is within this axis's
        configured safe range, raising ValueError if not - so an
        out-of-range waveform never reaches the galvo mirror.

        Parameters
        ----------
        values : array-like or scalar
            Value(s) in volts about to be written to this axis.

        Returns
        -------
        The input, unchanged, if valid (raises otherwise) - so this can be
        used inline: `self.z_array[1, :] = self._lateral_axis.validate(waveform)`.
        """
        values = np.asarray(values)
        if values.size == 0:
            return values
        vmin, vmax = float(np.min(values)), float(np.max(values))
        if not (
            self.voltage_range.within_range(Voltage(vmin))
            and self.voltage_range.within_range(Voltage(vmax))
        ):
            raise ValueError(
                f"Galvo axis {self.label!r} ({self.channel}): value(s) in "
                f"[{vmin:.3g}, {vmax:.3g}] V exceed configured safe range "
                f"{self.voltage_range.min} to {self.voltage_range.max}."
            )
        return values
