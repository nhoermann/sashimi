"""NI-DAQ driver for the optogenetics stimulation galvo pair + laser gate, on
a dedicated card separate from the imaging ScannerProcess's board.

Adapts dirigo's GalvoWaveformWriter (dirigo/plugins/scanners.py): a
background thread that continuously regenerates and rewrites the AO buffer,
rather than being driven by an external per-cycle write() call the way the
imaging ScanLoop drives NIBoards. Dirigo's line/frame-clock and
counter/frequency-divider machinery (built to synchronize galvo-galvo/
resonant-galvo raster scanning with a digitizer's frame acquisition) is not
ported - there is no digitizer or frame acquisition on this card, only
continuous galvo steering through a stimulation waveform, so only the
continuously-regenerating-buffer execution model is reused, not the parts
specific to camera/digitizer-synchronized point-scanning.

Not testable without the physical hardware - verify on real hardware before
relying on it, especially the exact nidaqmx digital-write API used for the
gate line.
"""

import threading
from contextlib import contextmanager

import numpy as np
import nidaqmx
from nidaqmx.constants import AcquisitionType, LineGrouping
from nidaqmx.stream_writers import AnalogMultiChannelWriter, DigitalSingleChannelWriter

from sashimi.hardware.optogenetics.interface import AbstractOptoInterface
from sashimi.hardware.scanning.galvo import GalvoAxis
from sashimi.waveforms import generate_stim_waveform


class OptoNIBoard(AbstractOptoInterface):
    def __init__(self, sample_rate, n_samples, conf):
        super().__init__(sample_rate, n_samples, conf)
        opto_conf = conf["opto_board"]

        self._x_axis = GalvoAxis(
            opto_conf["write"]["x_channel"],
            opto_conf["voltage_limits"]["x"],
            label="opto_x",
        )
        self._y_axis = GalvoAxis(
            opto_conf["write"]["y_channel"],
            opto_conf["voltage_limits"]["y"],
            label="opto_y",
        )
        self._gate_channel = opto_conf["write"]["gate_channel"]

        self._stim_parameters = None
        self._lock = threading.Lock()
        self._xy_galvo = (0.0, 0.0)
        self._gate = False

        self._ao_task = None
        self._do_task = None
        self._ao_writer = None
        self._do_writer = None
        self._writer_thread = None
        self._stop_event = threading.Event()

    def set_stim_parameters(self, stim_parameters):
        with self._lock:
            self._stim_parameters = stim_parameters

    @property
    def xy_galvo(self):
        return self._xy_galvo

    @property
    def gate(self):
        return self._gate

    def _generate_buffer(self):
        with self._lock:
            stim_parameters = self._stim_parameters

        if stim_parameters is None or not stim_parameters.rois:
            xy = np.zeros((2, self.n_samples))
            gate = np.zeros(self.n_samples, dtype=bool)
            return xy, gate

        xy, gate = generate_stim_waveform(
            stim_parameters.rois,
            self.sample_rate,
            self.n_samples,
            pattern=stim_parameters.pattern,
            spacing=stim_parameters.spacing,
            dwell_time=stim_parameters.dwell_time,
            transit_time=stim_parameters.transit_time,
            revolutions=stim_parameters.revolutions,
        )
        xy[0, :] = self._x_axis.validate(xy[0, :])
        xy[1, :] = self._y_axis.validate(xy[1, :])
        return xy, gate

    def _writer_loop(self):
        while not self._stop_event.is_set():
            xy, gate = self._generate_buffer()
            try:
                self._ao_writer.write_many_sample(xy)
                self._do_writer.write_many_sample_port_byte(gate.astype(np.uint8))
            except nidaqmx.errors.DaqError:
                # Task not yet started/being torn down - retry next cycle.
                continue
            self._xy_galvo = (xy[0, -1], xy[1, -1])
            self._gate = bool(gate[-1])

    def start(self):
        self._ao_task = nidaqmx.Task("Optogenetics galvo waveform")
        self._ao_task.ao_channels.add_ao_voltage_chan(self._x_axis.channel)
        self._ao_task.ao_channels.add_ao_voltage_chan(self._y_axis.channel)
        self._ao_task.timing.cfg_samp_clk_timing(
            rate=self.sample_rate,
            sample_mode=AcquisitionType.CONTINUOUS,
            samps_per_chan=self.n_samples,
        )
        self._ao_writer = AnalogMultiChannelWriter(self._ao_task.out_stream)

        self._do_task = nidaqmx.Task("Optogenetics laser gate")
        self._do_task.do_channels.add_do_chan(
            self._gate_channel, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
        )
        self._do_task.timing.cfg_samp_clk_timing(
            rate=self.sample_rate,
            sample_mode=AcquisitionType.CONTINUOUS,
            samps_per_chan=self.n_samples,
        )
        self._do_writer = DigitalSingleChannelWriter(self._do_task.out_stream)

        initial_xy, initial_gate = self._generate_buffer()
        self._ao_writer.write_many_sample(initial_xy)
        self._do_writer.write_many_sample_port_byte(initial_gate.astype(np.uint8))

        self._ao_task.start()
        self._do_task.start()

        self._stop_event.clear()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

    def stop(self):
        self._stop_event.set()
        if self._writer_thread is not None:
            self._writer_thread.join(timeout=5)
            self._writer_thread = None

        for task in (self._ao_task, self._do_task):
            if task is not None:
                task.stop()
                task.close()
        self._ao_task = None
        self._do_task = None
        self._xy_galvo = (0.0, 0.0)
        self._gate = False


@contextmanager
def open_opto_niboard(sample_rate, n_samples, conf) -> OptoNIBoard:
    board = OptoNIBoard(sample_rate, n_samples, conf)
    try:
        yield board
    finally:
        board.stop()
