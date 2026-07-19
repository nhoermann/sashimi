from sashimi.lightparam.param_qt import ParametrizedQt
from sashimi.lightparam import Param
from sashimi.lightparam.gui import ParameterGui


class BoolSettings(ParametrizedQt):
    def __init__(self):
        super().__init__()
        self.name = "test/bool_settings"
        self.enabled = Param(False, (0, 1))


def test_checkbox_control_refresh_widgets_does_not_crash(qtbot):
    # Regression test: ControlCheck.update_display() used to call
    # QCheckBox.setValue(), which doesn't exist (should be setChecked()).
    # Never caught before since sashimi's only other boolean Param used
    # gui=False, so no ControlCheck was ever built/refreshed.
    settings = BoolSettings()
    settings.enabled = True
    widget = ParameterGui(settings)
    qtbot.addWidget(widget)

    widget.refresh_widgets()  # must not raise

    checkbox = widget.param_widgets["enabled"].control
    assert checkbox.isChecked() is True

    settings.enabled = False
    widget.refresh_widgets()
    assert checkbox.isChecked() is False
