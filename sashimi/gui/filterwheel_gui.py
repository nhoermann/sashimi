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

        self.wid_filter_settings = ParameterGui(self.state.filterwheel_settings)
        
        self.state.filterwheel_settings.sig_param_changed.connect(self.set_filter)

        self.main_layout.addWidget(self.wid_filter_settings)
        
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(self.main_layout)
       
    def set_filter(self, new_filter):
        # Signal that is being sent is a dict in the form {'filter': 'MyFilter1'}
        self.state.filterwheel.filter = new_filter['filter']
        #print('Filter changed to (in UI): ', new_filter)