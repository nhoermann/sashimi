from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


class OptoWarning(Warning):
    """Raised (via warnings.warn) when the optogenetics stimulation waveform
    can't be generated/validated for the currently-set StimParameters - the
    board falls back to a laser-off buffer rather than crashing or freezing
    at its last output (see sashimi/hardware/optogenetics/ni.py)."""

    pass


@dataclass
class StimParameters:
    """One or several ROIs and the pattern used to scan them, passed from
    the GUI/State layer down to an AbstractOptoInterface. `rois` holds (M, 2)
    polygon vertex arrays (galvo-voltage units) for pattern="raster", or
    (center, radius) tuples for pattern="spiral" - see
    sashimi/waveforms.py's generate_stim_waveform, which this feeds.
    """

    rois: List = field(default_factory=list)
    pattern: str = "raster"
    dwell_time: float = 0.001
    transit_time: float = 0.0002
    spacing: float = 0.05
    revolutions: int = 3


class AbstractOptoInterface(ABC):
    """Interface for the optogenetics stimulation subsystem: a galvo X/Y pair
    plus a laser gate/blanking line, run independently of the imaging
    ScannerProcess (see sashimi/processes/optogenetics.py). The two are not
    hardware-triggered together - only temporally correlated afterwards via
    the shared ConcurrenceLogger timestamped log (see
    sashimi/processes/logging.py) and the saved experiment metadata.
    """

    def __init__(self, sample_rate, n_samples, conf):
        self.sample_rate = sample_rate
        self.n_samples = n_samples
        self.conf = conf

    @abstractmethod
    def start(self):
        """Start continuous output, using whatever stim parameters are
        currently set (see set_stim_parameters)."""
        pass

    @abstractmethod
    def stop(self):
        """Stop output and park the galvos / close the gate."""
        pass

    @abstractmethod
    def set_stim_parameters(self, stim_parameters):
        """Update the ROI(s)/pattern/dwell-time to scan; takes effect on the
        next waveform regeneration cycle, without needing to restart()."""
        pass

    @property
    @abstractmethod
    def xy_galvo(self):
        """Last galvo (x, y) position written, in volts - for logging only."""
        pass

    @property
    @abstractmethod
    def gate(self):
        """Last gate/blanking value written (True = laser may fire)."""
        pass
