import numpy as np
from multiprocessing import Manager as MultiprocessingManager
from queue import Empty
from typing import Optional
from sashimi.lightparam.param_qt import ParametrizedQt
from sashimi.lightparam import Param, ParameterTree
from sashimi.hardware.light_source.manager import LightSourceManager
from typing import Union

from sashimi.processes.scanning import ScannerProcess
from sashimi.hardware.scanning.scanloops import (
    ScanningState,
    ExperimentPrepareState,
    XYScanning,
    PlanarScanning,
    ZManual,
    ZSynced,
    ZScanning,
    TriggeringParameters,
    ScanParameters,
)
from sashimi.processes.external_communication import ExternalComm
from sashimi.processes.dispatcher import VolumeDispatcher
from sashimi.processes.logging import ConcurrenceLogger
from sashimi.processes.optogenetics import OptogeneticsProcess
from sashimi.hardware.optogenetics.interface import StimParameters
from multiprocessing import Event
import json
from sashimi.processes.camera import (
    CameraProcess,
    CamParameters,
    CameraMode,
    TriggerMode,
)
from sashimi.processes.streaming_save import StackSaver, SavingParameters, SavingStatus
from sashimi.events import LoggedEvent, SashimiEvents
from pathlib import Path
from enum import Enum
from sashimi.config import read_config
import time
from sashimi.utilities import clean_json, get_last_parameters

conf = read_config()


class GlobalState(Enum):
    PAUSED = 0
    PREVIEW = 1
    PLANAR_PREVIEW = 2
    VOLUME_PREVIEW = 3
    EXPERIMENT_RUNNING = 4


class SaveSettings(ParametrizedQt):
    def __init__(self):
        super().__init__()
        self.name = "experiment_settings"
        self.save_dir = Param(conf["default_paths"]["data"], gui=False)
        self.notification_email = Param("")
        self.overwrite_save_folder = Param(0, (0, 1), gui=False, loadable=False)


class TriggerSettings(ParametrizedQt):
    def __init__(self):
        super().__init__(self)
        self.name = "trigger_settings"
        self.experiment_duration = Param(5, (1, 50_000), unit="s")
        self.is_triggered = Param(True, [True, False], gui=False)


class ScanningSettings(ParametrizedQt):
    def __init__(self):
        super().__init__()
        self.name = "general/scanning_state"
        self.scanning_state = Param(
            "Paused",
            ["Paused", "Calibration", "Planar", "Volume"],
        )


scanning_to_global_state = dict(
    Paused=GlobalState.PAUSED,
    Calibration=GlobalState.PREVIEW,
    Planar=GlobalState.PLANAR_PREVIEW,
    Volume=GlobalState.VOLUME_PREVIEW,
)


class PlanarScanningSettings(ParametrizedQt):
    def __init__(self):
        super().__init__()
        self.name = "scanning/planar_scanning"
        self.lateral_range = Param((0, 0.5), (-2, 2))
        self.lateral_frequency = Param(500.0, (10, 1000), unit="Hz")
        self.frontal_range = Param((0, 0.5), (-2, 2))
        self.frontal_frequency = Param(500.0, (10, 1000), unit="Hz")


class CalibrationZSettings(ParametrizedQt):
    def __init__(self):
        super().__init__()
        self.name = "scanning/z_manual"
        self.piezo = Param(200.0, (0.0, 400.0), unit="um", gui="slider")
        self.lateral = Param(0.0, (-2.0, 2.0), gui="slider")
        self.frontal = Param(0.0, (-2.0, 2.0), gui="slider")


class SinglePlaneSettings(ParametrizedQt):
    def __init__(self):
        super().__init__()
        self.name = "scanning/z_single_plane"
        self.piezo = Param(200.0, (0.0, 400.0), unit="um", gui="slider")
        self.frequency = Param(1.0, (0.1, 1000), unit="planes/s (Hz)")


class ZRecordingSettings(ParametrizedQt):
    def __init__(self):
        super().__init__(self)
        self.name = "scanning/volumetric_recording"
        self.piezo_scan_range = Param((180.0, 220.0), (0.0, 400.0), unit="um")
        self.frequency = Param(3.0, (0.1, 100), unit="volumes/s (Hz)")
        self.n_planes = Param(4, (2, 100))
        self.n_skip_start = Param(0, (0, 20))
        self.n_skip_end = Param(0, (0, 20))


roi_size = [0, 0] + [
    r // conf["camera"]["default_binning"]
    for r in conf["camera"]["max_sensor_resolution"]
]


class CameraSettings(ParametrizedQt):
    def __init__(self):
        super().__init__()
        self.name = "camera/parameters"
        self.exposure_time = Param(
            conf["camera"]["default_exposure"], (1, 1000), unit="ms"
        )
        self.binning = Param(conf["camera"]["default_binning"], [1, 2, 4])
        self.roi = Param(
            roi_size, gui=False
        )  # order of params here is [hpos, vpos, hsize, vsize,]; h: horizontal, v: vertical


class LightSourceSettings(ParametrizedQt):
    def __init__(self, label="light_source", intensity_units="mock", max_intensity=40):
        super().__init__()
        # Must be unique per channel so distinct channels don't collide in the
        # settings_tree (see State.__init__).
        self.name = f"general/light_source/{label}"
        self.intensity = Param(0, (0, max_intensity), unit=intensity_units)


class OptogeneticsSettings(ParametrizedQt):
    def __init__(self):
        super().__init__()
        self.name = "general/optogenetics"
        self.pattern = Param("raster", ["raster", "spiral"])
        self.dwell_time_ms = Param(1.0, (0.01, 100), unit="ms")
        self.transit_time_ms = Param(0.2, (0.0, 50), unit="ms")
        self.spacing = Param(0.05, (0.001, 2.0), unit="V")
        self.revolutions = Param(3, (1, 20))


def convert_stim_parameters(settings: OptogeneticsSettings, calibration, pixel_rois):
    """Convert user-drawn ROIs (in camera pixel coordinates) into a
    StimParameters ready for OptogeneticsProcess, using the fitted
    pixel->galvo affine calibration (OptoCalibration.pixel_to_galvo).

    `pixel_rois` is always a list of (M, 2) pixel-coordinate polygons - the
    GUI only ever draws polygons (see optogenetics_gui.py's
    toggle_stimulation, which builds pixel_rois from a napari shapes layer
    locked to Mode.ADD_POLYGON), regardless of settings.pattern. For
    "spiral", each polygon is reduced to a covering circle: the center is
    the polygon's centroid and the radius is the largest distance from that
    center to any of its (galvo-mapped) vertices.
    """
    if settings.pattern == "raster":
        galvo_rois = [calibration.pixel_to_galvo(polygon) for polygon in pixel_rois]
    elif settings.pattern == "spiral":
        galvo_rois = []
        for polygon_px in pixel_rois:
            galvo_polygon = calibration.pixel_to_galvo(np.atleast_2d(polygon_px))
            center_galvo = galvo_polygon.mean(axis=0)
            radius_galvo = float(
                np.max(np.linalg.norm(galvo_polygon - center_galvo, axis=1))
            )
            galvo_rois.append((tuple(center_galvo), radius_galvo))
    else:
        raise ValueError(f"Unknown pattern {settings.pattern!r}")

    return StimParameters(
        rois=galvo_rois,
        pattern=settings.pattern,
        dwell_time=settings.dwell_time_ms / 1000,
        transit_time=settings.transit_time_ms / 1000,
        spacing=settings.spacing,
        revolutions=int(settings.revolutions),
    )


class StytraSettings(ParametrizedQt):
    """Which visual-stimulation protocol to run in stytra for this
    experiment. Sent to stytra alongside the existing lightsheet trigger
    (see sashimi/processes/external_communication.py); stytra's own
    protocol is currently fixed at its own launch time (Stytra(protocol=...)),
    so today this arrives as metadata stytra logs verbatim rather than a
    live protocol switch - see sashimi/hardware/external_trigger/stytra.py.
    """

    def __init__(self):
        super().__init__()
        self.name = "general/stytra"
        self.protocol_name = Param("")


class StytraCameraRoleSettings(ParametrizedQt):
    """One behavior camera's tracking config, matching stytra's role-based
    multi-camera schema (`cameras=[dict(role=..., tracking=dict(method=...))]`,
    see stytra/examples/heart_tail_tracking_exp.py). `role_name` identifies
    which physical camera this is (e.g. "tail_cam") and is not itself a Param
    since it's fixed for the lifetime of this settings object, not something
    the GUI lets the user retype.
    """

    def __init__(self, role_name):
        super().__init__()
        self.name = f"general/stytra/{role_name}"
        self.role_name = role_name
        self.enabled = Param(False, (0, 1))
        self.tracking_method = Param(
            "tail", ["tail", "heart_rate", "pectoral_fin", "none"]
        )


def convert_stytra_config(stytra_settings: StytraSettings, camera_role_settings):
    """Build the payload sent to stytra alongside the lightsheet trigger:
    a protocol name plus stytra's own role-based multi-camera tracking
    schema. `camera_role_settings` is a list of StytraCameraRoleSettings.
    """
    cameras = [
        dict(role=settings.role_name, tracking=dict(method=settings.tracking_method))
        for settings in camera_role_settings
        if settings.enabled and settings.tracking_method != "none"
    ]
    return dict(
        protocol_name=stytra_settings.protocol_name,
        stytra_config=dict(cameras=cameras),
    )


def convert_planar_params(planar: PlanarScanningSettings):
    return PlanarScanning(
        lateral=XYScanning(
            vmin=planar.lateral_range[0],
            vmax=planar.lateral_range[1],
            frequency=planar.lateral_frequency,
        ),
        frontal=XYScanning(
            vmin=planar.frontal_range[0],
            vmax=planar.frontal_range[1],
            frequency=planar.frontal_frequency,
        ),
    )


def convert_calibration_params(
    planar: PlanarScanningSettings, zsettings: CalibrationZSettings
):
    sp = ScanParameters(
        state=ScanningState.PLANAR,
        xy=convert_planar_params(planar),
        z=ZManual(**zsettings.params.values),
    )
    return sp


class Calibration(ParametrizedQt):
    def __init__(self):
        super().__init__()
        self.name = "general/calibration"
        self.z_settings = CalibrationZSettings()
        self.calibrations_points = []
        self.calibration = Param([(0, 0.01), (0, 0.01)], gui=False)

    def add_calibration_point(self):
        self.calibrations_points.append(
            (
                self.z_settings.piezo,
                self.z_settings.lateral,
                self.z_settings.frontal,
            )
        )
        self.calculate_calibration()

    def remove_calibration_point(self):
        if len(self.calibrations_points) > 0:
            self.calibrations_points.pop()
            self.calculate_calibration()

    def calculate_calibration(self):
        if len(self.calibrations_points) < 2:
            self.calibration = None
            return False

        calibration_data = np.array(self.calibrations_points)
        piezo_val = np.pad(
            calibration_data[:, 0:1],
            ((0, 0), (1, 0)),
            constant_values=1.0,
            mode="constant",
        )
        lateral_val = calibration_data[:, 1]
        frontal_val = calibration_data[:, 2]

        # solve least squares according to standard formula b = (XtX)^-1 * Xt * y
        piezo_cor = np.linalg.pinv(piezo_val.T @ piezo_val)

        self.calibration = [
            tuple(piezo_cor @ piezo_val.T @ galvo)
            for galvo in [lateral_val, frontal_val]
        ]

        return True


class OptoCalibration(ParametrizedQt):
    """Pixel (camera image) -> galvo voltage calibration for the
    optogenetics stimulation arm, which shares the imaging camera's optical
    path (per project decision - ROIs are drawn directly on the live camera
    view, see sashimi/gui/optogenetics_gui.py). Parallels the piezo->galvo
    `Calibration` class above, but fits a full 2D affine transform (offset +
    2x2 matrix) rather than a 1D linear one, since the camera and galvo axes
    may be rotated/sheared relative to each other.
    """

    def __init__(self):
        super().__init__()
        self.name = "general/opto_calibration"
        self.calibration_points = []  # list of (pixel_x, pixel_y, galvo_x, galvo_y)
        self.affine = Param(None, gui=False)  # (2, 3): [[a0,a1,a2], [b0,b1,b2]]

    def add_calibration_point(self, pixel_x, pixel_y, galvo_x, galvo_y):
        self.calibration_points.append((pixel_x, pixel_y, galvo_x, galvo_y))
        self.calculate_calibration()

    def remove_calibration_point(self):
        if len(self.calibration_points) > 0:
            self.calibration_points.pop()
            self.calculate_calibration()

    def calculate_calibration(self):
        # A 2D affine fit (offset + 2x2 matrix) needs at least 3
        # non-collinear points, same as fitting 3 unknowns per output axis.
        if len(self.calibration_points) < 3:
            self.affine = None
            return False

        calibration_data = np.array(self.calibration_points)
        pixel_xy = np.pad(
            calibration_data[:, 0:2],
            ((0, 0), (1, 0)),
            constant_values=1.0,
            mode="constant",
        )
        galvo_x = calibration_data[:, 2]
        galvo_y = calibration_data[:, 3]

        # solve least squares according to standard formula b = (XtX)^-1 * Xt * y
        pixel_cor = np.linalg.pinv(pixel_xy.T @ pixel_xy)

        # Stored as a list of tuples, not a numpy array: lightparam's
        # Param.__setattr__ compares old/new values with `!=` and expects a
        # scalar bool back, which a numpy array doesn't give (raises
        # "truth value of an array is ambiguous") - same reason the existing
        # piezo Calibration.calibration above is a list of tuples too.
        self.affine = [
            tuple(pixel_cor @ pixel_xy.T @ galvo_x),
            tuple(pixel_cor @ pixel_xy.T @ galvo_y),
        ]

        return True

    def pixel_to_galvo(self, pixel_points):
        """Convert an (N, 2) array of (pixel_x, pixel_y) points to (N, 2)
        galvo (x, y) voltages using the fitted affine transform."""
        if self.affine is None:
            raise ValueError(
                "Optogenetics calibration not set (need >= 3 calibration points)."
            )
        pixel_points = np.atleast_2d(pixel_points)
        padded = np.hstack([np.ones((pixel_points.shape[0], 1)), pixel_points])
        affine = np.array(self.affine)
        galvo_x = padded @ affine[0]
        galvo_y = padded @ affine[1]
        return np.stack([galvo_x, galvo_y], axis=1)


def get_voxel_size(
    scanning_settings: Union[ZRecordingSettings, SinglePlaneSettings],
    camera_settings: CameraSettings,
):
    binning = int(camera_settings.binning)

    if isinstance(scanning_settings, SinglePlaneSettings):
        inter_plane = 1
    else:
        scan_length = (
            scanning_settings.piezo_scan_range[1]
            - scanning_settings.piezo_scan_range[0]
        )
        inter_plane = scan_length / scanning_settings.n_planes

    return (
        inter_plane,
        conf["voxel_size"]["y"] * binning,
        conf["voxel_size"]["x"] * binning,
    )


def convert_save_params(
    save_settings: SaveSettings,
    scanning_settings: Union[ZRecordingSettings, SinglePlaneSettings],
    camera_settings: CameraSettings,
    trigger_settings: TriggerSettings,
):
    if isinstance(scanning_settings, SinglePlaneSettings):
        n_planes = 0
    else:
        n_planes = scanning_settings.n_planes - (
            scanning_settings.n_skip_start + scanning_settings.n_skip_end
        )

    return SavingParameters(
        output_dir=Path(save_settings.save_dir),
        n_planes=n_planes,
        notification_email=str(save_settings.notification_email),
        volumerate=scanning_settings.frequency,
        voxel_size=get_voxel_size(scanning_settings, camera_settings),
        crop=[
            int(item) for item in camera_settings.roi
        ],  # int conversion makes it json serializable
    )


def convert_single_plane_params(
    planar: PlanarScanningSettings,
    single_plane_setting: SinglePlaneSettings,
    calibration: Calibration,
):
    return ScanParameters(
        state=ScanningState.PLANAR,
        xy=convert_planar_params(planar),
        z=ZSynced(
            piezo=single_plane_setting.piezo,
            lateral_sync=tuple(calibration.calibration[0]),
            frontal_sync=tuple(calibration.calibration[1]),
        ),
        triggering=TriggeringParameters(frequency=single_plane_setting.frequency),
    )


def convert_volume_params(
    planar: PlanarScanningSettings,
    z_setting: ZRecordingSettings,
    calibration: Calibration,
):
    return ScanParameters(
        state=ScanningState.VOLUMETRIC,
        xy=convert_planar_params(planar),
        z=ZScanning(
            piezo_min=z_setting.piezo_scan_range[0],
            piezo_max=z_setting.piezo_scan_range[1],
            frequency=z_setting.frequency,
            lateral_sync=tuple(calibration.calibration[0]),
            frontal_sync=tuple(calibration.calibration[1]),
        ),
        triggering=TriggeringParameters(
            n_planes=z_setting.n_planes,
            n_skip_start=z_setting.n_skip_start,
            n_skip_end=z_setting.n_skip_end,
            frequency=None,
        ),
    )


class State:
    def __init__(self):
        self.conf = read_config()
        self.sample_rate = conf["sample_rate"]

        self.logger = ConcurrenceLogger("main")

        self.calibration_ref = None
        self.waveform = None
        self.current_plane = 0
        self.stop_event = LoggedEvent(self.logger, SashimiEvents.CLOSE_ALL)
        self.restart_event = LoggedEvent(self.logger, SashimiEvents.RESTART_SCANNING)
        self.experiment_start_event = LoggedEvent(
            self.logger, SashimiEvents.SEND_EXT_TRIGGER
        )
        self.noise_subtraction_active = LoggedEvent(
            self.logger, SashimiEvents.NOISE_SUBTRACTION_ACTIVE, Event()
        )
        self.is_saving_event = LoggedEvent(self.logger, SashimiEvents.IS_SAVING)

        # The even active during scanning preparation (before first real camera trigger)
        self.is_waiting_event = LoggedEvent(
            self.logger, SashimiEvents.WAITING_FOR_TRIGGER
        )

        self.experiment_state = ExperimentPrepareState.PREVIEW
        self.status = ScanningSettings()

        self.scanner = ScannerProcess(
            stop_event=self.stop_event,
            restart_event=self.restart_event,
            waiting_event=self.is_waiting_event,
            sample_rate=self.sample_rate,
        )
        self.camera_settings = CameraSettings()
        self.trigger_settings = TriggerSettings()

        self.settings_tree = ParameterTree()

        self.pause_after = False
        if self.conf["scopeless"]:
            self.light_source_manager = LightSourceManager(
                [{"name": "mock", "port": None, "intensity_units": "mock"}]
            )
        else:
            self.light_source_manager = LightSourceManager(conf["light_sources"])
        self.camera = CameraProcess(
            stop_event=self.stop_event,
            wait_event=self.scanner.wait_signal,
            exp_trigger_event=self.experiment_start_event,
        )

        self.multiprocessing_manager = MultiprocessingManager()

        self.experiment_duration_queue = self.multiprocessing_manager.Queue()

        self.external_comm = ExternalComm(
            stop_event=self.stop_event,
            experiment_start_event=self.experiment_start_event,
            is_saving_event=self.is_saving_event,
            is_waiting_event=self.is_waiting_event,
            duration_queue=self.experiment_duration_queue,
        )

        self.saver = StackSaver(
            stop_event=self.stop_event,
            is_saving_event=self.is_saving_event,
            duration_queue=self.experiment_duration_queue,
        )

        self.dispatcher = VolumeDispatcher(
            stop_event=self.stop_event,
            saving_signal=self.saver.saving_signal,
            wait_signal=self.scanner.wait_signal,
            noise_subtraction_on=self.noise_subtraction_active,
            camera_queue=self.camera.image_queue,
            saver_queue=self.saver.save_queue,
        )

        # Runs independently of self.scanner (own board, own clock - see
        # sashimi/hardware/optogenetics/ni.py's module docstring for why).
        self.optogenetics = OptogeneticsProcess(
            stop_event=self.stop_event,
            sample_rate=self.sample_rate,
        )

        self.camera_settings = CameraSettings()
        self.save_settings = SaveSettings()

        self.settings_tree = ParameterTree()

        self.global_state = GlobalState.PAUSED
        self.current_exp_state = GlobalState.PAUSED
        self.prev_exp_state = self.current_exp_state

        self.planar_setting = PlanarScanningSettings()
        # One LightSourceSettings per configured channel (a channel is either a
        # whole unit, e.g. Cobolt, or one of a combiner's several channels,
        # e.g. Toptica CLE/MLE - see LightSourceManager.channels).
        self.light_source_settings = [
            LightSourceSettings(
                label=channel.label,
                intensity_units=channel.intensity_units,
            )
            for channel in self.light_source_manager.channels
        ]

        self.save_status: Optional[SavingStatus] = None

        self.single_plane_settings = SinglePlaneSettings()
        self.volume_setting = ZRecordingSettings()
        self.calibration = Calibration()
        self.opto_calibration = OptoCalibration()
        self.optogenetics_settings = OptogeneticsSettings()
        self.stytra_settings = StytraSettings()
        self.stytra_camera_roles = [
            StytraCameraRoleSettings(role_name=role)
            for role in ["tail_cam", "heart_cam", "fin_cam"]
        ]

        for setting in [
            self.planar_setting,
            *self.light_source_settings,
            self.single_plane_settings,
            self.volume_setting,
            self.calibration,
            self.calibration.z_settings,
            self.opto_calibration,
            self.optogenetics_settings,
            self.stytra_settings,
            *self.stytra_camera_roles,
            self.camera_settings,
            self.save_settings,
        ]:
            self.settings_tree.add(setting)

        self.status.sig_param_changed.connect(self.change_global_state)

        self.planar_setting.sig_param_changed.connect(self.send_scansave_settings)
        self.calibration.z_settings.sig_param_changed.connect(self.send_scan_settings)
        self.single_plane_settings.sig_param_changed.connect(self.send_scan_settings)
        self.volume_setting.sig_param_changed.connect(self.send_scan_settings)
        self.stytra_settings.sig_param_changed.connect(self.send_stytra_config)
        for role_settings in self.stytra_camera_roles:
            role_settings.sig_param_changed.connect(self.send_stytra_config)

        self.save_settings.sig_param_changed.connect(self.send_scansave_settings)

        self.camera.start()
        self.scanner.start()
        self.external_comm.start()
        self.saver.start()
        self.dispatcher.start()
        self.optogenetics.start()

        self.current_binning = conf["camera"]["default_binning"]
        self.send_scansave_settings()
        self.send_stytra_config()
        self.logger.log_message("initialized")

        self.voxel_size = None

    def restore_tree(self, restore_file):
        with open(restore_file, "r") as f:
            self.settings_tree.deserialize(json.load(f))

    def save_tree(self, save_file):
        with open(save_file, "w") as f:
            json.dump(clean_json(self.settings_tree.serialize()), f)

    def change_global_state(self):
        self.global_state = scanning_to_global_state[self.status.scanning_state]
        self.send_camera_settings()
        self.send_scansave_settings()

    def send_camera_settings(self):
        self.camera.image_queue.clear()
        self.camera.parameter_queue.put(self.camera_params)

    def send_scan_settings(self, param_changed=None):
        # Restart scanning loop if scanning params have changed:
        if self.global_state == GlobalState.VOLUME_PREVIEW:
            self.restart_event.set()

        self.send_scansave_settings()

    @property
    def n_planes(self):
        if self.global_state == GlobalState.VOLUME_PREVIEW:
            return (
                self.volume_setting.n_planes
                - self.volume_setting.n_skip_start
                - self.volume_setting.n_skip_end
            )
        else:
            return 1

    @property
    def save_params(self):
        if self.global_state == GlobalState.PLANAR_PREVIEW:
            save_p = convert_save_params(
                self.save_settings,
                self.single_plane_settings,
                self.camera_settings,
                self.trigger_settings,
            )
        else:
            save_p = convert_save_params(
                self.save_settings,
                self.volume_setting,
                self.camera_settings,
                self.trigger_settings,
            )
        return save_p

    @property
    def scan_params(self):
        """Return parameters for the scanning, depending on the state."""
        if self.global_state == GlobalState.PAUSED:
            params = ScanParameters(state=ScanningState.PAUSED)

        elif self.global_state == GlobalState.PREVIEW:
            params = convert_calibration_params(
                self.planar_setting, self.calibration.z_settings
            )

        elif self.global_state == GlobalState.PLANAR_PREVIEW:
            params = convert_single_plane_params(
                self.planar_setting,
                self.single_plane_settings,
                self.calibration,
            )

        elif self.global_state == GlobalState.VOLUME_PREVIEW:
            params = convert_volume_params(
                self.planar_setting, self.volume_setting, self.calibration
            )
        else:
            return

        params.experiment_state = self.experiment_state
        return params

    @property
    def camera_params(self):
        camera_params = CamParameters(
            exposure_time=self.camera_settings.exposure_time,
            binning=int(self.camera_settings.binning),
            roi=tuple(self.camera_settings.roi),
        )

        camera_params.trigger_mode = (
            TriggerMode.FREE
            if self.global_state == GlobalState.PREVIEW
            or self.global_state == GlobalState.PLANAR_PREVIEW
            else TriggerMode.EXTERNAL_TRIGGER
        )
        if self.global_state == GlobalState.PAUSED:
            camera_params.camera_mode = CameraMode.PAUSED
        else:
            camera_params.camera_mode = CameraMode.PREVIEW

        return camera_params

    @property
    def all_settings(self):
        all_settings = dict(scanning=self.scan_params, camera=self.camera_params)

        if self.waveform is not None:
            pulses = self.calculate_pulse_times() * self.sample_rate
            try:
                pulse_log = self.waveform[pulses.astype(int)]
                all_settings["piezo_log"] = dict(trigger=pulse_log.tolist())
            except IndexError:
                pass

        return all_settings

    def send_scansave_settings(self):
        # Make sure that current plane is updated if we changed number of planes
        if self.global_state == GlobalState.VOLUME_PREVIEW:
            self.current_plane = min(self.current_plane, self.n_planes - 1)

        self.scanner.parameter_queue.put(self.scan_params)
        self.external_comm.current_settings_queue.put(self.all_settings)

        self.voxel_size = get_voxel_size(self.volume_setting, self.camera_settings)
        self.saver.saving_parameter_queue.put(self.save_params)
        self.dispatcher.n_planes_queue.put(self.n_planes)

    def start_experiment(self) -> None:
        """
        Sets all the signals and cleans the queue
        to trigger the start of the experiment
        """
        self.current_exp_state = GlobalState.EXPERIMENT_RUNNING
        self.logger.log_message("started experiment")
        self.scanner.wait_signal.set()
        self.send_scansave_settings()
        self.restart_event.set()
        self.saver.save_queue.empty()
        self.camera.image_queue.empty()
        time.sleep(0.01)
        self.is_saving_event.set()

    def end_experiment(self) -> None:
        """
        Sets all the signals and cleans the queue
        to trigger the end of the experiment
        """
        self.logger.log_message("experiment ended")
        self.is_saving_event.clear()
        self.experiment_start_event.clear()
        self.saver.save_queue.clear()
        self.send_scansave_settings()
        self.current_exp_state = GlobalState.PAUSED

    def is_exp_started(self) -> bool:
        """
        check if the experiment has started:
        looks for tha change in the value hold by current_exp_state

        Returns:
            bool
        """
        if (
            self.current_exp_state == GlobalState.EXPERIMENT_RUNNING
            and self.prev_exp_state == GlobalState.PAUSED
        ):
            self.prev_exp_state = GlobalState.EXPERIMENT_RUNNING
            return True
        else:
            return False

    def is_exp_ended(self) -> bool:
        """
        check if the experiment has ended:
        looks for tha change in the value hold by current_exp_state

        Returns:
            bool
        """
        if (
            self.prev_exp_state == GlobalState.EXPERIMENT_RUNNING
            and self.current_exp_state == GlobalState.PAUSED
        ):
            self.prev_exp_state = GlobalState.PAUSED
            return True
        else:
            return False

    def obtain_noise_average(self, n_images=50):
        """Obtains average noise of n_images to subtract to acquired,
        both for display and saving.

        Parameters
        ----------
        n_images : int
            Number of frames to average.

        """
        self.noise_subtraction_active.clear()

        channels = self.light_source_manager.channels
        saved_intensities = [
            settings.intensity for settings in self.light_source_settings
        ]
        for channel in channels:
            channel.intensity = 0
        n_image = 0
        while n_image < n_images:
            current_volume = self.get_volume()
            if current_volume is not None:
                current_image = current_volume[0, :, :]
                if n_image == 0:
                    calibration_set = np.empty(
                        shape=(n_images, *current_image.shape),
                        dtype=current_volume.dtype,
                    )
                calibration_set[n_image, :, :] = current_image
                n_image += 1

        self.calibration_ref = np.mean(calibration_set, axis=0).astype(
            dtype=current_volume.dtype
        )
        for channel, intensity in zip(channels, saved_intensities):
            channel.intensity = intensity

        self.noise_subtraction_active.set()

        self.dispatcher.calibration_ref_queue.put(self.calibration_ref)

    def reset_noise_subtraction(self):
        self.calibration_ref = None
        self.noise_subtraction_active.clear()

    def get_volume(self):
        # TODO consider get_last_parameters method
        try:
            return self.dispatcher.viewer_queue.get(timeout=0.001)
        except Empty:
            return None

    def get_save_status(self) -> Optional[SavingStatus]:
        return get_last_parameters(self.saver.saved_status_queue)

    def get_triggered_frame_rate(self):
        return get_last_parameters(self.camera.triggered_frame_rate_queue)

    def get_waveform(self):
        return get_last_parameters(self.scanner.waveform_queue)

    def calculate_pulse_times(self):
        return np.arange(
            self.volume_setting.n_skip_start,
            self.volume_setting.n_planes - self.volume_setting.n_skip_end,
        ) / (self.volume_setting.frequency * self.volume_setting.n_planes)

    def set_trigger_mode(self, mode: bool):
        if mode:
            self.external_comm.is_triggered_event.set()
        else:
            self.external_comm.is_triggered_event.clear()

    def send_manual_duration(self):
        self.experiment_duration_queue.put(self.trigger_settings.experiment_duration)

    def send_stim_parameters(self, pixel_rois):
        """Convert GUI-drawn ROIs (camera pixel coordinates) to galvo
        voltages via the optogenetics calibration and push them to
        OptogeneticsProcess. `pixel_rois` is empty to stop stimulation."""
        stim_parameters = convert_stim_parameters(
            self.optogenetics_settings, self.opto_calibration, pixel_rois
        )
        self.optogenetics.parameter_queue.put(stim_parameters)

    def send_stytra_config(self):
        """Push the current protocol/tracking selection to ExternalComm, to
        be sent alongside the lightsheet settings on the next trigger."""
        stytra_config = convert_stytra_config(
            self.stytra_settings, self.stytra_camera_roles
        )
        self.external_comm.stytra_config_queue.put(stytra_config)

    def get_tracking_data_path(self):
        """Path the external program (e.g. stytra) reported it saved the
        most recent run's data under, if it reported one - see
        AbstractComm.trigger_and_receive_duration."""
        return get_last_parameters(self.external_comm.tracking_data_queue)

    def wrap_up(self):
        self.stop_event.set()
        self.light_source_manager.close()

        self.scanner.join(timeout=10)
        self.saver.join(timeout=10)
        self.camera.join(timeout=10)
        self.external_comm.join(timeout=10)
        self.dispatcher.join(timeout=10)
        self.optogenetics.join(timeout=10)
        self.logger.close()
