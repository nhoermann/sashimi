"""Process running the optogenetics stimulation subsystem, independent of
the imaging ScannerProcess (see sashimi/processes/scanning.py) - its own
board/NI card and its own clock. The two are never hardware-triggered
together; they're temporally correlated afterwards via the shared
ConcurrenceLogger timestamped log (see sashimi/processes/logging.py) and the
saved experiment metadata, per the confirmed design in
sashimi/hardware/optogenetics/ni.py's module docstring.
"""

from multiprocessing import Queue
from queue import Empty

from sashimi.hardware.optogenetics.mock import open_mock_optoboard
from sashimi.hardware.optogenetics.interface import StimParameters
from sashimi.processes.logging import LoggingProcess
from sashimi.events import LoggedEvent
from sashimi.config import read_config

try:
    from sashimi.hardware.optogenetics.ni import open_opto_niboard

    OPTO_NI_AVAILABLE = True
except ImportError:
    OPTO_NI_AVAILABLE = False

conf = read_config()

# Dictionary of options for the context within which the stimulation has to run.
opto_conf_dict = dict(mock=open_mock_optoboard)
if OPTO_NI_AVAILABLE:
    opto_conf_dict["ni"] = open_opto_niboard


class OptogeneticsProcess(LoggingProcess):
    """Runs the optogenetics stimulation loop, mirroring ScannerProcess's
    process/queue/event conventions. Unlike ScannerProcess, this loop is not
    driven by a per-cycle write() - the board (see
    sashimi/hardware/optogenetics/ni.py) owns its own continuous-output
    background thread once started(); this process just relays new
    StimParameters to it and starts/stops stimulation as ROIs are
    added/cleared.
    """

    def __init__(
        self,
        stop_event: LoggedEvent,
        n_samples_waveform=10000,
        sample_rate=40000,
    ):
        super().__init__(name="optogenetics")
        self.stop_event = stop_event.new_reference(self.logger)
        self.parameter_queue = Queue()
        self.n_samples = n_samples_waveform
        self.sample_rate = sample_rate
        self.parameters = StimParameters()

    def run(self):
        self.logger.log_message("started")
        configurator = opto_conf_dict[conf["opto_board"]["name"]]
        started = False
        with configurator(self.sample_rate, self.n_samples, conf) as board:
            while not self.stop_event.is_set():
                try:
                    new_params = self.parameter_queue.get(timeout=0.05)
                except Empty:
                    continue

                self.parameters = new_params
                board.set_stim_parameters(self.parameters)

                if self.parameters.rois and not started:
                    board.start()
                    started = True
                    self.logger.log_message("started stimulation")
                elif not self.parameters.rois and started:
                    board.stop()
                    started = False
                    self.logger.log_message("stopped stimulation")

            if started:
                board.stop()
        self.close_log()
