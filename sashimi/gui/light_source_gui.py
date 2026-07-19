from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QWidget,
)
from sashimi.lightparam.gui import ParameterGui


class LightSourceChannelWidget(QWidget):
    """One row of laser channel controls: label, ON/OFF toggle, intensity
    slider - the same layout sashimi has always used for its single laser.
    LightSourceWidget stacks one of these per configured channel.
    """

    def __init__(self, channel, settings, timer):
        super().__init__()
        self.channel = channel
        self.settings = settings

        self.main_layout = QHBoxLayout()

        self.lbl_text = QLabel(channel.label)

        self.btn_off = QPushButton("ON")
        self.btn_off.clicked.connect(self.toggle)

        self.main_layout.addWidget(self.lbl_text)
        self.main_layout.addWidget(self.btn_off)
        self.wid_settings = ParameterGui(self.settings)
        self.main_layout.addWidget(self.wid_settings)

        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(self.main_layout)
        self.laser_on = False
        self.previous_current = self.settings.intensity
        timer.timeout.connect(self.update_current)

    def update_current(self):
        if self.laser_on and self.previous_current != self.settings.intensity:
            self.channel.intensity = self.settings.intensity
        self.previous_current = self.settings.intensity

    def toggle(self):
        self.laser_on = not self.laser_on
        if self.laser_on:
            self.btn_off.setText("OFF")
            self.channel.intensity = self.previous_current
        else:
            self.btn_off.setText("ON")
            self.channel.intensity = 0

    def turn_off(self):
        if self.laser_on:
            self.btn_off.click()


class LightSourceWidget(QWidget):
    """Stacks one LightSourceChannelWidget per configured laser channel (a
    channel is either a whole unit, e.g. Cobolt, or one of a combiner's
    several channels, e.g. Toptica CLE/MLE)."""

    def __init__(self, state, timer):
        super().__init__()
        self.state = state

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.channel_widgets = [
            LightSourceChannelWidget(channel, settings, timer)
            for channel, settings in zip(
                state.light_source_manager.channels, state.light_source_settings
            )
        ]
        for wid in self.channel_widgets:
            self.main_layout.addWidget(wid)

        self.setLayout(self.main_layout)

    def turn_all_off(self):
        for wid in self.channel_widgets:
            wid.turn_off()
