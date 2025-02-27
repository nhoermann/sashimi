from PyQt5.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QLabel,
    QWidget,
)

from lightparam.gui import ParameterGui
from lightparam import Param
from lightparam.param_qt import ParametrizedQt

class FilterWheelWidget(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state

        self.main_layout = QHBoxLayout()

        # self.state.filterwheel_settings.sig_param_changed.connect(self.update_on_bin_change)

        self.lbl_text = QLabel("Filter")

        self.wid_filter_settings = ParameterGui(self.state.filterwheel_settings)
        self.wid_filter_settings.currentTextChanged.connect(self.set_filter)

        self.main_layout.addWidget(self.lbl_text)
        self.main_layout.addWidget(self.wid_filter_settings)
        
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(self.main_layout)
       
    def set_filter(self, new_filter):
        self.state.filterwheel.filter = new_filter
        print('Filter changed to (in UI): ', new_filter)