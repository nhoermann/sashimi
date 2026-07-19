import numpy as np
import pytest

from sashimi.waveforms import (
    TriangleWaveform,
    SmoothTriangleWaveform,
    point_dwell_sequence,
    raster_fill_waveform,
    spiral_waveform,
    gate_from_roi_membership,
    generate_stim_waveform,
    _points_in_polygon,
)
from sashimi.hardware.scanning.units import Angle, Voltage, VoltageRange, AngleRange
from sashimi.hardware.scanning.galvo import GalvoAxis, validate_ni_channel


def _dirigo_reference_period(amplitude, rtf, n_samples):
    """Direct port of dirigo's GalvoScannerViaNI.generate_waveform
    (LINEAR_BIDIRECTIONAL case, dirigo/plugins/scanners.py), evaluated over
    exactly one period at `n_samples` points - used only to check that
    SmoothTriangleWaveform's continuous-phase reformulation (T=1) matches
    dirigo's original fixed-buffer-per-period algorithm sample-for-sample.

    dirigo's own formula (as transcribed here, verbatim) overshoots the
    nominal `amplitude` by a factor of (1+rtf)/(2*rtf) - confirmed
    numerically, not a transcription slip. SmoothTriangleWaveform corrects
    for this so its output actually stays within [vmin, vmax]; apply the
    same correction here so this reference checks the corrected shape, not
    dirigo's overshoot.
    """
    T = n_samples
    amplitude = amplitude * (2 * rtf) / (1 + rtf)
    A = amplitude / 2
    w0 = (T / 4) * (1 - rtf)
    w1 = (T / 4) * (1 + rtf)
    w2 = (T / 4) * (3 - rtf)
    w3 = (T / 4) * (3 + rtf)
    m = 4 * A / (T * rtf)
    k = 16 * A / (T**2 * rtf * (1 - rtf))

    t0 = np.arange(0, w0 - 0.5)
    t1 = np.arange(t0[-1] + 1, w1 - 0.5)
    t2 = np.arange(t1[-1] + 1, w2 - 0.5)
    t3 = np.arange(t2[-1] + 1, w3 - 0.5)
    t4 = np.arange(t3[-1] + 1, T - 0.5)

    f0 = 0.5 * k * (t0**2 - w0**2) - A
    f1 = m * (t1 - w0) - A
    f2 = 0.5 * k * (w1**2 - t2**2) + 0.5 * k * T * (t2 - w1) + A
    f3 = m * (w2 - t3) + A
    f4 = 0.5 * k * (t4**2 - w3**2) + k * T * (w3 - t4) - A

    return np.concatenate((f0, f1, f2, f3, f4), axis=0)


@pytest.mark.parametrize("rtf", [0.5, 0.7, 0.9])
def test_smooth_triangle_matches_dirigo_reference(rtf):
    n_samples = 2000
    amplitude = 4.0
    vmin, vmax = -2.0, 2.0  # peak-to-peak = amplitude

    reference = _dirigo_reference_period(amplitude, rtf, n_samples)

    wave = SmoothTriangleWaveform(
        frequency=1.0, vmin=vmin, vmax=vmax, ramp_time_fraction=rtf
    )
    # Match dirigo's own discrete sample indexing (integer position / n), not
    # sample-center offsets, so this compares like-for-like phase points.
    t = np.arange(n_samples) / n_samples
    ours = wave.values(t)

    np.testing.assert_allclose(ours, reference, atol=1e-6)


def test_smooth_triangle_is_continuous_across_period_boundary():
    wave = SmoothTriangleWaveform(
        frequency=2.0, vmin=-3, vmax=5, ramp_time_fraction=0.8
    )
    t = np.linspace(0, 3 / 2.0, 300_000)  # 3 periods
    values = wave.values(t)
    # No sample-to-sample jump should exceed a small multiple of the average step:
    max_step = np.max(np.abs(np.diff(values)))
    avg_step = np.mean(np.abs(np.diff(values)))
    assert max_step < 20 * avg_step


def test_smooth_triangle_stays_within_bounds():
    vmin, vmax = -1.5, 2.5
    wave = SmoothTriangleWaveform(
        frequency=3.0, vmin=vmin, vmax=vmax, ramp_time_fraction=0.6
    )
    t = np.linspace(0, 5, 50_000)
    values = wave.values(t)
    assert values.min() >= vmin - 1e-9
    assert values.max() <= vmax + 1e-9


def test_smooth_triangle_rejects_invalid_ramp_time_fraction():
    with pytest.raises(ValueError):
        SmoothTriangleWaveform(ramp_time_fraction=0)
    with pytest.raises(ValueError):
        SmoothTriangleWaveform(ramp_time_fraction=1)


def test_smooth_vs_plain_triangle_same_shape_different_corners():
    # Both should span the same range and have the same period, but the
    # smooth version should never reach the plain triangle's max slope
    # (that's the whole point - bounded acceleration at the turnaround).
    t = np.linspace(0, 2, 20_000)
    plain = TriangleWaveform(frequency=1.0, vmin=0, vmax=1)
    smooth = SmoothTriangleWaveform(
        frequency=1.0, vmin=0, vmax=1, ramp_time_fraction=0.5
    )

    assert np.isclose(plain.values(t).min(), smooth.values(t).min(), atol=1e-2)
    assert np.isclose(plain.values(t).max(), smooth.values(t).max(), atol=1e-2)


def test_galvo_axis_validates_range():
    axis = GalvoAxis("Dev1/ao0", {"min_val": -5, "max_val": 5}, label="lateral")
    axis.validate(np.array([-4.9, 0, 4.9]))  # should not raise

    with pytest.raises(ValueError):
        axis.validate(np.array([-4.9, 0, 6.0]))


def test_galvo_axis_rejects_malformed_channel():
    with pytest.raises(ValueError):
        GalvoAxis("not_a_channel", {"min_val": -5, "max_val": 5})


def test_validate_ni_channel_accepts_common_formats():
    assert validate_ni_channel("Dev1/ao0") == "Dev1/ao0"
    assert validate_ni_channel("/Dev1/PFI4") == "/Dev1/PFI4"


def test_units_angle_and_voltage_range():
    assert AngleRange("-5 deg", "5 deg").within_range(Angle("0 deg"))
    assert not VoltageRange(-5, 5).within_range(Voltage(10))


UNIT_SQUARE = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])


def test_points_in_polygon_basic():
    xs = np.array([0.5, 1.5, 0.5, -0.5])
    ys = np.array([0.5, 0.5, 1.5, 0.5])
    inside = _points_in_polygon(UNIT_SQUARE, xs, ys)
    assert list(inside) == [True, False, False, False]


def test_point_dwell_sequence_shape_and_gating():
    points = [(0, 0), (1, 0), (1, 1)]
    dwell, transit = 5, 2
    xy, gate = point_dwell_sequence(points, dwell, transit)

    n_per_point = dwell + transit
    assert xy.shape == (2, len(points) * n_per_point)
    assert gate.shape == (len(points) * n_per_point,)
    # Every dwell segment gated on, every transit segment gated off:
    for i in range(len(points)):
        start = i * n_per_point
        assert not gate[start : start + transit].any()
        assert gate[start + transit : start + n_per_point].all()
        # dwell segment sits exactly at the target point:
        np.testing.assert_array_equal(
            xy[:, start + transit : start + n_per_point],
            np.tile(np.array(points[i])[:, None], dwell),
        )


def test_point_dwell_sequence_wraps_transit_to_last_point():
    points = [(0, 0), (10, 0)]
    xy, gate = point_dwell_sequence(points, dwell_samples=1, transit_samples=4)
    # First point's transit segment should move FROM the last point (10, 0)
    # TOWARD the first point (0, 0), confirming the cyclic wraparound.
    first_transit = xy[:, :4]
    assert first_transit[0, 0] == pytest.approx(10.0)
    assert first_transit[0, -1] < first_transit[0, 0]


def test_raster_fill_waveform_points_fall_inside_polygon():
    xy, gate = raster_fill_waveform(UNIT_SQUARE, spacing=0.2, dwell_samples=3)
    dwell_xy = xy[:, gate]
    assert dwell_xy.shape[1] > 0
    inside = _points_in_polygon(UNIT_SQUARE, dwell_xy[0], dwell_xy[1])
    assert inside.all()


def test_raster_fill_waveform_raises_if_nothing_inside():
    # A rectangle's bounding-box corner is always one of its own vertices, so
    # the grid (which always starts exactly at x_min/y_min) would always
    # include at least that corner point regardless of spacing. Use a
    # diamond instead, whose bounding-box corners sit outside the polygon,
    # to genuinely test the "nothing falls inside" case.
    diamond = np.array([[0.5, 0], [1, 0.5], [0.5, 1], [0, 0.5]])
    with pytest.raises(ValueError):
        raster_fill_waveform(diamond, spacing=10.0, dwell_samples=1)


def test_spiral_waveform_stays_within_radius():
    center, radius = (2.0, -1.0), 3.0
    xy, gate = spiral_waveform(center, radius, n_points=1000, revolutions=4)
    dist = np.hypot(xy[0] - center[0], xy[1] - center[1])
    assert dist.max() <= radius + 1e-9
    assert gate.all()


def test_gate_from_roi_membership_matches_manual_check():
    xy = np.array([[0.5, 5.0, 0.9], [0.5, 5.0, 0.1]])
    gate = gate_from_roi_membership(xy, [UNIT_SQUARE])
    assert list(gate) == [True, False, True]


def test_generate_stim_waveform_raster_fills_exact_length():
    n_samples = 10_000
    # sample_rate must be high enough that the default transit_time (0.2 ms)
    # rounds to at least 1 sample - matches sashimi's real ~40 kHz rate.
    xy, gate = generate_stim_waveform(
        [UNIT_SQUARE], sample_rate=40_000, n_samples=n_samples, pattern="raster"
    )
    assert xy.shape == (2, n_samples)
    assert gate.shape == (n_samples,)
    assert gate.any() and not gate.all()  # some transit, some dwell


def test_generate_stim_waveform_spiral_fills_exact_length():
    n_samples = 5_000
    xy, gate = generate_stim_waveform(
        [((0, 0), 2.0)], sample_rate=1000, n_samples=n_samples, pattern="spiral"
    )
    assert xy.shape == (2, n_samples)
    assert gate.all()


def test_generate_stim_waveform_multiple_rois_all_represented():
    square_a = UNIT_SQUARE
    square_b = UNIT_SQUARE + 10  # disjoint region, far away
    xy, gate = generate_stim_waveform(
        [square_a, square_b],
        sample_rate=1000,
        n_samples=20_000,
        pattern="raster",
        dwell_time=0.01,
    )
    dwell_xy = xy[:, gate]
    near_a = _points_in_polygon(square_a, dwell_xy[0], dwell_xy[1])
    near_b = _points_in_polygon(square_b, dwell_xy[0], dwell_xy[1])
    assert near_a.any()
    assert near_b.any()


def test_generate_stim_waveform_rejects_empty_rois():
    with pytest.raises(ValueError):
        generate_stim_waveform([], sample_rate=1000, n_samples=100)
