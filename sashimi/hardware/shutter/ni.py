from sashimi.hardware.shutter.interface import AbstractShutter, ShutterWarning

import nidaqmx
from nidaqmx.constants import LineGrouping

from warnings import warn

class NIShutter(AbstractShutter):
    def __init__(self, port=None):
        super().__init__(port)
        self.port =  port


    def set_shutter(self, command):
        """Sets shutter"""
        try:
            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(self.port, line_grouping=LineGrouping.CHAN_PER_LINE)
                task.write([command], auto_start=True)
        except:
            warn("Shutter unchanged", ShutterWarning)

    def close(self):
        pass

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, command):
        self._status = command
        self.set_shutter(command)
        # print("NI Shutter set to: ", str(self._status))