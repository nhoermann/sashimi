"""GUI for the optogenetics stimulation subsystem: draws ROIs on the same
live camera view used for imaging (per project decision - the stimulation
beam shares the imaging optical path), runs the pixel->galvo calibration,
and starts/stops stimulation. Reuses the same napari-shapes-layer + button
state-machine pattern already used for the camera ROI in camera_gui.py, and
the same row-of-controls docked-widget style used elsewhere, per instruction
to keep sashimi's existing GUI design rather than introduce a new one.
"""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
)
from napari.layers.shapes._shapes_constants import Mode
from napari.layers.points._points_constants import Mode as PointsMode
import numpy as np

from sashimi.lightparam.gui import ParameterGui
from sashimi.lightparam.param_qt import ParametrizedQt
from sashimi.lightparam import Param
from sashimi.hardware.optogenetics.interface import StimParameters

#: Half-width (galvo volts) of the tiny square ROI used to park the beam at
#: a fixed manual position during calibration (see park_at_manual_position).
_PARK_HALF_WIDTH = 0.01


class ManualGalvoSettings(ParametrizedQt):
    """Manual galvo X/Y position, used only to park the beam at a known spot
    for pixel->galvo calibration - not part of the saved experiment
    parameters, so intentionally not added to State's settings_tree."""

    def __init__(self, voltage_limits):
        super().__init__()
        self.name = "optogenetics/manual_galvo"
        self.galvo_x = Param(
            0.0,
            (voltage_limits["x"]["min_val"], voltage_limits["x"]["max_val"]),
            unit="V",
            gui="slider",
        )
        self.galvo_y = Param(
            0.0,
            (voltage_limits["y"]["min_val"], voltage_limits["y"]["max_val"]),
            unit="V",
            gui="slider",
        )


class OptogeneticsSettingsWidget(QWidget):
    """Widget to draw optogenetic stimulation ROIs on the live camera view,
    calibrate the pixel->galvo mapping, and start/stop stimulation.

    Parameters
    ----------
    state : State object
    wid_display : ViewingWidget
    """

    def __init__(self, state, wid_display):
        super().__init__()
        self.state = state
        self.opto_roi_layer = wid_display.opto_roi_layer
        self.calib_point_layer = wid_display.opto_calib_point_layer

        self.manual_galvo_settings = ManualGalvoSettings(
            state.conf["opto_board"]["voltage_limits"]
        )

        self.setLayout(QVBoxLayout())

        self.wid_pattern_settings = ParameterGui(self.state.optogenetics_settings)
        self.layout().addWidget(self.wid_pattern_settings)

        # --- ROI drawing controls ---
        self.btn_draw_rois = QPushButton("Draw ROIs")
        self.btn_draw_rois.setCheckable(True)
        self.btn_draw_rois.clicked.connect(self.toggle_roi_drawing)
        self.btn_clear_rois = QPushButton("Clear ROIs")
        self.btn_clear_rois.clicked.connect(self.clear_rois)

        roi_row = QHBoxLayout()
        roi_row.addWidget(self.btn_draw_rois)
        roi_row.addWidget(self.btn_clear_rois)
        self.layout().addLayout(roi_row)

        # --- Stimulation control ---
        self.btn_stim = QPushButton("Start stimulation")
        self.btn_stim.setCheckable(True)
        self.btn_stim.clicked.connect(self.toggle_stimulation)
        self.layout().addWidget(self.btn_stim)

        # --- Calibration controls ---
        self.wid_manual_galvo = ParameterGui(self.manual_galvo_settings)
        self.btn_calib_mode = QPushButton("Calibration mode")
        self.btn_calib_mode.setCheckable(True)
        self.btn_calib_mode.clicked.connect(self.toggle_calibration_mode)
        self.btn_park = QPushButton("Park at manual position")
        self.btn_park.clicked.connect(self.park_at_manual_position)
        self.btn_add_calib_point = QPushButton("Add calibration point")
        self.btn_add_calib_point.clicked.connect(self.add_calibration_point)
        self.btn_remove_calib_point = QPushButton("Remove last calibration point")
        self.btn_remove_calib_point.clicked.connect(self.remove_calibration_point)
        self.lbl_calib = QLabel("")

        self.layout().addWidget(self.btn_calib_mode)
        self.layout().addWidget(self.wid_manual_galvo)
        self.layout().addWidget(self.btn_park)
        self.layout().addWidget(self.btn_add_calib_point)
        self.layout().addWidget(self.btn_remove_calib_point)
        self.layout().addWidget(self.lbl_calib)

        self.update_calib_label()

    def toggle_roi_drawing(self, checked):
        self.opto_roi_layer.visible = checked
        self.opto_roi_layer.mode = Mode.ADD_POLYGON if checked else Mode.PAN_ZOOM

    def clear_rois(self):
        self.opto_roi_layer.data = []

    def toggle_stimulation(self, checked):
        if checked:
            # napari shape coordinates are (row, col) i.e. (pixel_y, pixel_x);
            # flip to (pixel_x, pixel_y) to match add_calibration_point's
            # convention, since OptoCalibration's affine fit is only valid if
            # points are given in the same axis order it was fitted on.
            pixel_rois = [
                np.asarray(shape)[:, ::-1] for shape in self.opto_roi_layer.data
            ]
            if not pixel_rois:
                self.btn_stim.setChecked(False)
                return
            self.state.send_stim_parameters(pixel_rois)
            self.btn_stim.setText("Stop stimulation")
        else:
            self.state.send_stim_parameters([])
            self.btn_stim.setText("Start stimulation")

    def toggle_calibration_mode(self, checked):
        self.calib_point_layer.visible = checked
        self.calib_point_layer.mode = PointsMode.ADD if checked else PointsMode.PAN_ZOOM

    def park_at_manual_position(self):
        x = self.manual_galvo_settings.galvo_x
        y = self.manual_galvo_settings.galvo_y
        w = _PARK_HALF_WIDTH
        tiny_square = np.array(
            [[x - w, y - w], [x + w, y - w], [x + w, y + w], [x - w, y + w]]
        )
        self.state.optogenetics.parameter_queue.put(
            StimParameters(
                rois=[tiny_square], pattern="raster", dwell_time=0.01, transit_time=0
            )
        )

    def add_calibration_point(self):
        if len(self.calib_point_layer.data) == 0:
            return
        # napari point coordinates are (row, col) i.e. (pixel_y, pixel_x).
        pixel_y, pixel_x = self.calib_point_layer.data[-1]
        self.state.opto_calibration.add_calibration_point(
            pixel_x,
            pixel_y,
            self.manual_galvo_settings.galvo_x,
            self.manual_galvo_settings.galvo_y,
        )
        self.update_calib_label()

    def remove_calibration_point(self):
        self.state.opto_calibration.remove_calibration_point()
        self.update_calib_label()

    def update_calib_label(self):
        n_points = len(self.state.opto_calibration.calibration_points)
        status = (
            "calibrated"
            if self.state.opto_calibration.affine is not None
            else "not calibrated"
        )
        self.lbl_calib.setText(f"{n_points} calibration point(s) ({status})")
