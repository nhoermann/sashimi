import numpy as np
import pytest

from sashimi.state import OptoCalibration, OptogeneticsSettings, convert_stim_parameters


def _known_affine_transform(pixel_xy, a, b):
    """galvo = a[0] + a[1]*px + a[2]*py, similarly for b - the same model
    OptoCalibration.calculate_calibration fits."""
    px, py = pixel_xy
    return a[0] + a[1] * px + a[2] * py, b[0] + b[1] * px + b[2] * py


def test_opto_calibration_recovers_known_affine_transform():
    # An arbitrary affine transform with rotation/shear/offset, since that's
    # exactly the case a 1D linear fit (like the existing piezo Calibration)
    # couldn't handle - the whole reason this is a 2D affine fit.
    a = (0.5, 0.02, -0.01)
    b = (-0.3, 0.005, 0.03)

    calib = OptoCalibration()
    pixel_points = [(0, 0), (100, 0), (0, 100), (50, 200), (300, 50)]
    for px, py in pixel_points:
        gx, gy = _known_affine_transform((px, py), a, b)
        calib.add_calibration_point(px, py, gx, gy)

    assert calib.affine is not None
    np.testing.assert_allclose(calib.affine[0], a, atol=1e-8)
    np.testing.assert_allclose(calib.affine[1], b, atol=1e-8)

    galvo = calib.pixel_to_galvo([(20, 30)])
    expected = _known_affine_transform((20, 30), a, b)
    np.testing.assert_allclose(galvo[0], expected, atol=1e-8)


def test_opto_calibration_needs_at_least_three_points():
    calib = OptoCalibration()
    calib.add_calibration_point(0, 0, 0, 0)
    calib.add_calibration_point(1, 0, 1, 0)
    assert calib.affine is None

    with pytest.raises(ValueError):
        calib.pixel_to_galvo([(0, 0)])

    calib.add_calibration_point(0, 1, 0, 1)
    assert calib.affine is not None


def test_opto_calibration_remove_point_recomputes():
    calib = OptoCalibration()
    for px, py, gx, gy in [(0, 0, 0, 0), (1, 0, 1, 0), (0, 1, 0, 1), (1, 1, 1, 1)]:
        calib.add_calibration_point(px, py, gx, gy)
    assert calib.affine is not None

    calib.remove_calibration_point()
    calib.remove_calibration_point()
    assert calib.affine is None  # down to 2 points, below the minimum of 3


def test_convert_stim_parameters_raster_converts_polygon_vertices():
    calib = OptoCalibration()
    # Identity-like transform (offset only) for a simple, checkable case:
    for px, py, gx, gy in [
        (0, 0, 1, 1),
        (10, 0, 11, 1),
        (0, 10, 1, 11),
    ]:
        calib.add_calibration_point(px, py, gx, gy)

    settings = OptogeneticsSettings()
    settings.pattern = "raster"
    pixel_square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]])

    stim_params = convert_stim_parameters(settings, calib, [pixel_square])

    assert stim_params.pattern == "raster"
    assert len(stim_params.rois) == 1
    np.testing.assert_allclose(
        stim_params.rois[0], pixel_square + 1, atol=1e-8
    )  # offset-only transform: galvo = pixel + 1


def test_convert_stim_parameters_spiral_converts_center_and_radius():
    calib = OptoCalibration()
    # Pure 2x scale transform: galvo = 2 * pixel
    for px, py, gx, gy in [(0, 0, 0, 0), (1, 0, 2, 0), (0, 1, 0, 2)]:
        calib.add_calibration_point(px, py, gx, gy)

    settings = OptogeneticsSettings()
    settings.pattern = "spiral"

    stim_params = convert_stim_parameters(settings, calib, [((5, 5), 3.0)])

    assert stim_params.pattern == "spiral"
    center, radius = stim_params.rois[0]
    np.testing.assert_allclose(center, (10, 10), atol=1e-8)
    assert radius == pytest.approx(6.0, abs=1e-8)  # 2x scale doubles radius too
