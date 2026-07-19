import numpy as np
from warnings import warn

from sashimi.hardware.cameras.interface import (
    AbstractCamera,
    TriggerMode,
    CameraException,
    CameraWarning,
)
from sashimi.config import read_config

try:
    from pyvcam import pvc
    from pyvcam.camera import Camera as PyVcamCamera

    PVCAM_AVAILABLE = True
except ImportError:
    PVCAM_AVAILABLE = False
    warn(
        "pyvcam not installed, Kinetix camera control not available. "
        "Install it (and the vendor PVCAM SDK/driver) with `pip install pyvcam`.",
        CameraWarning,
    )

conf = read_config()

# Kinetix (and other PVCAM cameras) name their trigger/exposure modes as
# strings looked up in Camera.exp_modes; these are the standard PVCAM names.
# Verify against the actual `cam.exp_modes` dict on the real camera, since
# the exact wording can vary by PVCAM version.
_TRIGGER_MODE_NAMES = {
    TriggerMode.FREE: "Internal Trigger",
    TriggerMode.EXTERNAL_TRIGGER: "Edge Trigger",
}

# How long a single get_frames() call blocks waiting for a new frame before
# giving up and returning no frames this cycle (matches the ~100ms Hamamatsu
# uses for its DCAMWAIT_START timeout).
_POLL_TIMEOUT_MS = 100


class KinetixCamera(AbstractCamera):
    """Driver for Teledyne Photometrics Kinetix (and other PVCAM-based)
    cameras, built on Photometrics' official `pyvcam` wrapper around the
    PVCAM SDK.

    Requires the PVCAM driver/runtime to be installed on the acquisition PC
    (not pip-installable) and `pip install pyvcam` on top of it. Not testable
    without the physical camera - verify on real hardware before relying on
    it for acquisition.
    """

    def __init__(self, camera_id, max_sensor_resolution):
        super().__init__(camera_id, max_sensor_resolution)

        if not PVCAM_AVAILABLE:
            raise CameraException(
                "pyvcam is not installed; Kinetix camera control is unavailable."
            )

        pvc.init_pvcam()
        detected_cameras = list(PyVcamCamera.detect_camera())
        if camera_id >= len(detected_cameras):
            raise CameraException(
                f"No PVCAM camera found at index {camera_id} "
                f"(found {len(detected_cameras)})."
            )
        self.camera = detected_cameras[camera_id]
        self.camera.open()

        self._binning = 1
        self._roi = (0, 0) + self.max_sensor_resolution
        self._trigger_mode = TriggerMode.EXTERNAL_TRIGGER
        self.trigger_mode = self._trigger_mode

        self.exposure_time = conf["camera"]["default_exposure"]
        self._last_fps = 1000 / self.exposure_time

        self._live = False

    @property
    def binning(self):
        return self._binning

    @binning.setter
    def binning(self, n_bin):
        self._binning = n_bin
        self.camera.binning = (n_bin, n_bin)

    @property
    def exposure_time(self):
        return self.camera.exp_time

    @exposure_time.setter
    def exposure_time(self, exp_val):
        self.camera.exp_time = int(round(exp_val))

    @property
    def frame_rate(self):
        return self._last_fps

    @property
    def roi(self):
        return self._roi

    @roi.setter
    def roi(self, exp_val: tuple):
        """`exp_val` is expressed in the current (post-binning) displayed
        pixel grid, matching the convention used by the Hamamatsu driver and
        by CameraSettings.roi in state.py - so it is scaled up by the binning
        factor to full-sensor pixels before being sent to the camera, since
        PVCAM's ROI is always expressed in full-sensor pixel coordinates.
        """
        self._roi = tuple(i * self.binning for i in exp_val)
        x_min, y_min, x_size, y_size = self._roi
        self.camera.set_roi(x_min, y_min, x_size, y_size)

    @property
    def trigger_mode(self):
        return self._trigger_mode

    @trigger_mode.setter
    def trigger_mode(self, exp_val: TriggerMode):
        self._trigger_mode = exp_val
        self.camera.exp_mode = _TRIGGER_MODE_NAMES[exp_val]

    def start_acquisition(self):
        if not self._live:
            self.camera.start_live(exp_time=int(round(self.exposure_time)))
            self._live = True

    def stop_acquisition(self):
        if self._live:
            self.camera.stop_live()
            self._live = False

    def get_frames(self):
        if not self._live:
            return []
        try:
            frame_obj, fps, _ = self.camera.poll_frame(
                timeout_ms=_POLL_TIMEOUT_MS, oldest_frame=True, copy_data=True
            )
        except Exception:
            # pyvcam raises on poll timeout when no frame is ready yet -
            # equivalent to Hamamatsu's DCAMWAIT timing out.
            return []

        self._last_fps = fps
        frame = np.reshape(frame_obj["pixel_data"], self.frame_shape)
        return [frame]

    @property
    def frame_shape(self):
        return (self._roi[3] // self.binning, self._roi[2] // self.binning)

    def shutdown(self):
        super().shutdown()
        self.camera.close()
        pvc.uninit_pvcam()
