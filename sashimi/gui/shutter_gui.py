from PyQt5.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QLabel,
    QWidget,
)

import qdarkstyle

# from lightparam.gui import ParameterGui

class ShutterWidget(QWidget):
    def __init__(self, state, timer):
        super().__init__()
        self.state = state

        self.main_layout = QHBoxLayout()

        self.lbl_text = QLabel("Shutter")

        self.btn_off = QPushButton("ON")
        self.btn_off.clicked.connect(self.toggle)

        self.main_layout.addWidget(self.lbl_text)
        self.main_layout.addWidget(self.btn_off)
        
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(self.main_layout)

        self.shutter_open = False

        self.style = qdarkstyle.load_stylesheet_pyqt5()
        
    def toggle(self):
        self.shutter_open = not self.shutter_open
        if self.shutter_open:
            self.btn_off.setText("OFF")
            self.btn_off.setStyleSheet('background-color: red;')
            self.state.shutter.status = True
        else:
            self.btn_off.setText("ON")
            self.btn_off.setStyleSheet(self.style)
            self.state.shutter.status = False
