"""GUI for selecting a stytra visual-stimulation protocol and which
behavior cameras/tracking methods (tail/heart/fin) to run alongside
imaging. Deepens the existing zmq trigger link (see
sashimi/processes/external_communication.py,
sashimi/hardware/external_trigger/stytra.py) rather than replacing it.
Follows the same ParameterGui-per-settings-object, row-of-widgets docked
pattern used elsewhere, per instruction to keep sashimi's existing GUI
design.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from sashimi.lightparam.gui import ParameterGui


class StytraSettingsWidget(QWidget):
    """Widget to pick a stytra protocol name and, per behavior camera role
    (tail/heart/fin), whether it's enabled and which tracking method to use.

    Parameters
    ----------
    state : State object
    timer : QTimer
    """

    def __init__(self, state, timer):
        super().__init__()
        self.state = state

        self.setLayout(QVBoxLayout())

        self.wid_protocol = ParameterGui(self.state.stytra_settings)
        self.layout().addWidget(self.wid_protocol)

        self.role_widgets = []
        for role_settings in self.state.stytra_camera_roles:
            row = QHBoxLayout()
            row.addWidget(QLabel(role_settings.role_name))
            wid_role = ParameterGui(role_settings)
            row.addWidget(wid_role)
            self.layout().addLayout(row)
            self.role_widgets.append(wid_role)

        self.lbl_tracking_data_path = QLabel("")
        self.layout().addWidget(self.lbl_tracking_data_path)

        timer.timeout.connect(self.update_tracking_data_path)

    def update_tracking_data_path(self):
        path = self.state.get_tracking_data_path()
        if path is not None:
            self.lbl_tracking_data_path.setText(f"Last tracking data: {path}")
