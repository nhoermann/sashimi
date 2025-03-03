from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QLineEdit,
    QLabel,
)
from lightparam.gui import ParameterGui
from lightparam.gui.collapsible_widget import CollapsibleWidget
from sashimi.gui.waveform_gui import WaveformWidget

import numpy as np


class PlanarScanningWidget(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.setLayout(QVBoxLayout())
        self.wid_planar = ParameterGui(state.planar_setting)
        self.layout().addWidget(self.wid_planar)


class SinglePlaneScanningWidget(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.setLayout(QVBoxLayout())
        self.wid_singleplane = ParameterGui(state.single_plane_settings)
        self.layout().addWidget(self.wid_singleplane)


class VolumeScanningWidget(QWidget):
    def __init__(self, state, timer):
        super().__init__()
        self.state = state
        self.timer = timer
        self.setLayout(QVBoxLayout())
        self.wid_volume = ParameterGui(state.volume_setting)
        self.chk_pause = QCheckBox("Pause after experiment")

        self.delta_z_layout = QHBoxLayout()
        self.delta_z_label = QLabel("Δz (µm)")
        self.delta_z_display = QLineEdit()
        self.delta_z_display.setReadOnly(True)
        self.delta_z_layout.setContentsMargins(0, 0, 0, 0)
        self.delta_z_layout.addWidget(self.delta_z_label)
        self.delta_z_layout.addWidget(self.delta_z_display)

        self.wid_wave = WaveformWidget(timer=self.timer, state=self.state)
        self.wid_collapsible_wave = CollapsibleWidget(
            child=self.wid_wave, name="Piezo impulse-response waveform"
        )
        self.wid_collapsible_wave.toggle_collapse()

        self.layout().addWidget(self.wid_volume)
        self.layout().addLayout(self.delta_z_layout)
        self.layout().addWidget(self.chk_pause)
        self.layout().addWidget(self.wid_collapsible_wave)

        self.chk_pause.clicked.connect(self.change_pause_status)

        self.chk_pause.click()

        self.state.volume_setting.sig_param_changed.connect(self.update_delta_z_display)

        self.update_delta_z_display()

    def change_pause_status(self):
        self.state.pause_after = self.chk_pause.isChecked()

    def update_delta_z_display(self):
        piezo_scan_range = self.state.volume_setting.piezo_scan_range
        z_range = abs(piezo_scan_range[1]-piezo_scan_range[0])
        n_planes = self.state.volume_setting.n_planes
        n_skip_start = self.state.volume_setting.n_skip_start
        n_skip_end = self.state.volume_setting.n_skip_end
        n_planes = n_planes - n_skip_start - n_skip_end
        delta_z = np.divide(z_range, n_planes)
        delta_z = np.round(delta_z, 2)
        self.delta_z_display.setText(str(delta_z))