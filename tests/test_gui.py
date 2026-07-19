from sashimi.gui.main_gui import MainWindow
from sashimi.gui.light_source_gui import LightSourceWidget
from sashimi.state import State, TriggerSettings, LightSourceSettings
from sashimi.hardware.light_source.manager import LightSourceManager
import qdarkstyle
from PyQt5.QtCore import Qt, QTimer
from split_dataset import SplitDataset


class MockEvt:
    def accept(self):
        pass


class FakeStateWithTwoLasers:
    """Minimal stand-in for State exposing just what LightSourceWidget needs,
    so this test doesn't have to spin up the full hardware/process stack to
    check multi-channel layout."""

    def __init__(self):
        self.light_source_manager = LightSourceManager(
            [
                {"name": "mock", "port": "COM1", "intensity_units": "mW"},
                {"name": "mock", "port": "COM2", "intensity_units": "mW"},
            ]
        )
        self.light_source_settings = [
            LightSourceSettings(label=channel.label, intensity_units="mW")
            for channel in self.light_source_manager.channels
        ]


def test_light_source_widget_multiple_channels(qtbot):
    state = FakeStateWithTwoLasers()
    timer = QTimer()
    widget = LightSourceWidget(state, timer)
    qtbot.addWidget(widget)

    assert len(widget.channel_widgets) == 2
    assert widget.channel_widgets[0].channel.label == "COM1"
    assert widget.channel_widgets[1].channel.label == "COM2"

    # Turning one channel on shouldn't affect the other:
    widget.channel_widgets[0].previous_current = 3
    widget.channel_widgets[0].toggle()
    assert widget.channel_widgets[0].channel.intensity == 3
    assert widget.channel_widgets[1].channel.intensity == 0

    widget.turn_all_off()
    assert widget.channel_widgets[0].channel.intensity == 0
    assert not widget.channel_widgets[0].laser_on


def test_main(qtbot, temp_path):
    st = State()
    style = qdarkstyle.load_stylesheet_pyqt5()
    main_window = MainWindow(st, style)
    main_window.show()
    qtbot.wait(300)

    # go to calibration and volumetric mode:
    main_window.wid_status.setCurrentIndex(1)
    qtbot.wait(300)
    main_window.wid_status.setCurrentIndex(3)

    # Manually update new directory (to avoid nasty pop up window for filesystem):
    st.save_settings.save_dir = str(temp_path)
    main_window.wid_save_options.set_locationbutton()
    st.send_scansave_settings()

    # Wait to send and receive parameters:
    qtbot.wait(10000)

    qtbot.mouseClick(main_window.toolbar.experiment_toggle_btn, Qt.LeftButton, delay=1)

    # wait end of the experiment:
    qtbot.wait(TriggerSettings().experiment_duration + 5000)

    # try opening the result:
    SplitDataset(temp_path / "original")

    main_window.closeEvent(MockEvt())
    qtbot.wait(1000)
