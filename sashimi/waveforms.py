import numpy as np
from numba import jit


class Waveform:
    def __init__(self, *args, **kwargs):
        pass

    def values(self, t):
        return np.zeros(len(self.t))


class ConstantWaveform(Waveform):
    def __init__(self, *args, constant_value=0, **kwargs):
        super().__init__()
        self.constant_value = constant_value

    def values(self, t):
        return np.full(len(t), self.constant_value)


class SawtoothWaveform(Waveform):
    def __init__(self, *args, frequency=1, vmin=0, vmax=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.vmin = vmin
        self.vmax = vmax
        self.frequency = frequency

    def values(self, t):
        tf = t * self.frequency
        return (tf - np.floor(tf)) * (self.vmax - self.vmin) + self.vmin


class RecordedWaveform(Waveform):
    def __init__(self, *args, recording, **kwargs):
        super().__init__(*args, **kwargs)
        self.recording = recording
        self.i_sample = 0

    def values(self, t):
        out = self.recording[self.i_sample : self.i_sample + len(t)]
        self.i_sample = (self.i_sample + len(t)) % self.recording.shape[0]
        return out


class TriangleWaveform(Waveform):
    def __init__(self, *args, frequency=1, vmin=0, vmax=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.vmin = vmin
        self.vmax = vmax
        self.frequency = frequency

    def values(self, t):
        tf = t * self.frequency
        return (
            self.vmin
            + (self.vmax - self.vmin) / 2
            + +(self.vmax - self.vmin)
            * (np.abs((tf - np.floor(tf + 1 / 2))) - 0.25)
            * 2
        )


class SmoothTriangleWaveform(Waveform):
    """Acceleration-limited triangle wave: a `ramp_time_fraction` portion of
    each period is a constant-velocity linear ramp, with the remainder spent
    in smooth (quadratic, continuous-velocity) turns at the peak and trough,
    instead of TriangleWaveform's instantaneous direction reversal. Reduces
    mechanical ringing in real galvo mirrors at the turnaround.

    Ported from dirigo's GalvoScannerViaNI.generate_waveform
    (LINEAR_BIDIRECTIONAL case, dirigo/plugins/scanners.py), adapted from
    dirigo's fixed-length-buffer-per-period evaluation to sashimi's
    continuous phase-based Waveform.values(t) interface.
    """

    def __init__(
        self, *args, frequency=1, vmin=0, vmax=1, ramp_time_fraction=0.9, **kwargs
    ):
        super().__init__(*args, **kwargs)
        if not (0 < ramp_time_fraction < 1):
            raise ValueError(
                f"ramp_time_fraction must be strictly between 0 and 1, "
                f"got {ramp_time_fraction}."
            )
        self.vmin = vmin
        self.vmax = vmax
        self.frequency = frequency
        self.ramp_time_fraction = ramp_time_fraction

    def values(self, t):
        half_amplitude = (self.vmax - self.vmin) / 2  # desired half peak-to-peak
        mid = (self.vmax + self.vmin) / 2
        rtf = self.ramp_time_fraction
        tau = (t * self.frequency) % 1.0  # phase within current period, [0, 1)

        # dirigo's algebra below (transcribed from
        # GalvoScannerViaNI.generate_waveform) actually overshoots the
        # nominal amplitude by a factor of (1+rtf)/(2*rtf) - confirmed
        # numerically against dirigo's own formula, not a transcription
        # error here. Pre-scale by the inverse factor so the waveform this
        # class produces actually stays within [vmin, vmax] as documented,
        # since that guarantee matters for GalvoAxis's downstream validation.
        amplitude = half_amplitude * (2 * rtf) / (1 + rtf)

        w0 = (1 - rtf) / 4
        w1 = (1 + rtf) / 4
        w2 = (3 - rtf) / 4
        w3 = (3 + rtf) / 4
        m = 4 * amplitude / rtf
        k = 16 * amplitude / (rtf * (1 - rtf))

        out = np.empty_like(tau, dtype=float)

        in_bottom_corner_start = tau < w0
        in_up_ramp = (tau >= w0) & (tau < w1)
        in_top_corner = (tau >= w1) & (tau < w2)
        in_down_ramp = (tau >= w2) & (tau < w3)
        in_bottom_corner_end = tau >= w3

        out[in_bottom_corner_start] = (
            0.5 * k * (tau[in_bottom_corner_start] ** 2 - w0**2) - amplitude
        )
        out[in_up_ramp] = m * (tau[in_up_ramp] - w0) - amplitude
        out[in_top_corner] = (
            0.5 * k * (w1**2 - tau[in_top_corner] ** 2)
            + 0.5 * k * (tau[in_top_corner] - w1)
            + amplitude
        )
        out[in_down_ramp] = m * (w2 - tau[in_down_ramp]) + amplitude
        out[in_bottom_corner_end] = (
            0.5 * k * (tau[in_bottom_corner_end] ** 2 - w3**2)
            + k * (w3 - tau[in_bottom_corner_end])
            - amplitude
        )

        return out + mid


@jit(nopython=True)
def set_impulses(buffer, n_planes, n_skip_start, n_skip_end, high=5):
    buffer[:] = 0
    n_between_planes = int(round(len(buffer) / n_planes))
    for i in range(n_skip_start, n_planes - n_skip_end):
        buffer[i * n_between_planes] = high


def _points_in_polygon(polygon, xs, ys):
    """Ray-casting point-in-polygon test, vectorized over a grid of query
    points. `polygon` is an (M, 2) array of (x, y) vertices; `xs`/`ys` are
    same-shape arrays of query point coordinates.
    """
    polygon = np.asarray(polygon, dtype=float)
    xv, yv = polygon[:, 0], polygon[:, 1]
    n_vertices = len(polygon)
    inside = np.zeros(xs.shape, dtype=bool)
    j = n_vertices - 1
    for i in range(n_vertices):
        xi, yi = xv[i], yv[i]
        xj, yj = xv[j], yv[j]
        # Avoid a divide-by-zero for horizontal edges (yj == yi): such edges
        # never satisfy the crossing condition on the left of it, so the
        # edge case's exact intersection value is never used.
        denom = yj - yi if yj != yi else 1.0
        crosses = (yi > ys) != (yj > ys)
        intersects = crosses & (xs < (xj - xi) * (ys - yi) / denom + xi)
        inside ^= intersects
        j = i
    return inside


def point_dwell_sequence(points, dwell_samples, transit_samples=0):
    """Build a (xy[2, N], gate[N]) waveform that dwells at each of `points`
    (a list/array of (x, y) galvo-voltage waypoints) for `dwell_samples`
    samples (gated on), optionally preceded by a `transit_samples`-long
    linear move from the previous point (gated off).

    Points are treated as a closed loop - the last point transits back to
    the first - so the result tiles seamlessly when repeated continuously
    (as the optogenetics board does, see sashimi/hardware/optogenetics/ni.py).
    """
    points = np.asarray(points, dtype=float)
    if len(points) == 0:
        raise ValueError("points must be non-empty.")

    n_points = len(points)
    n_per_point = transit_samples + dwell_samples
    xy = np.zeros((2, n_points * n_per_point))
    gate = np.zeros(n_points * n_per_point, dtype=bool)

    for i in range(n_points):
        prev_point = points[i - 1]  # wraps to points[-1] when i == 0
        target = points[i]
        start = i * n_per_point

        if transit_samples > 0:
            frac = np.linspace(0, 1, transit_samples, endpoint=False)
            xy[:, start : start + transit_samples] = (
                prev_point[:, None] + (target - prev_point)[:, None] * frac
            )

        dwell_start = start + transit_samples
        xy[:, dwell_start : dwell_start + dwell_samples] = target[:, None]
        gate[dwell_start : dwell_start + dwell_samples] = True

    return xy, gate


def raster_fill_waveform(polygon, spacing, dwell_samples, transit_samples=0):
    """Generate a raster grid of points filling the interior of `polygon`
    (an (M, 2) array of (x, y) galvo-voltage vertices), spaced `spacing`
    volts apart, and turn it into a dwell-and-transit waveform (see
    point_dwell_sequence). Row scan direction alternates (boustrophedon) to
    minimize transit distance between consecutive points.
    """
    polygon = np.asarray(polygon, dtype=float)
    (x_min, y_min), (x_max, y_max) = polygon.min(axis=0), polygon.max(axis=0)

    xs_grid = np.arange(x_min, x_max + spacing, spacing)
    ys_grid = np.arange(y_min, y_max + spacing, spacing)

    points = []
    for row_idx, y in enumerate(ys_grid):
        xs = xs_grid if row_idx % 2 == 0 else xs_grid[::-1]
        mask = _points_in_polygon(polygon, xs, np.full_like(xs, y))
        points.extend((x, y) for x in xs[mask])

    if not points:
        raise ValueError(
            "No raster points fall inside the given polygon at this spacing."
        )

    return point_dwell_sequence(points, dwell_samples, transit_samples)


def spiral_waveform(center, radius, n_points, revolutions=3):
    """Generate a continuous spiral trajectory covering a circular region of
    `radius` (galvo-voltage units) around `center`, gated on throughout
    since the whole path stays inside the target circle (no fly-back).
    """
    if n_points < 2:
        raise ValueError("n_points must be at least 2.")
    theta = np.linspace(0, 2 * np.pi * revolutions, n_points)
    r = radius * theta / theta[-1]
    xy = np.vstack([center[0] + r * np.cos(theta), center[1] + r * np.sin(theta)])
    gate = np.ones(n_points, dtype=bool)
    return xy, gate


def gate_from_roi_membership(xy_waveform, polygons):
    """Given an already-computed (2, N) galvo trajectory and a list of ROI
    polygons (each an (M, 2) array of (x, y) vertices, in the same
    coordinate space as xy_waveform), return a boolean (N,) mask of which
    samples fall inside any of the ROIs - usable as a laser gate signal, or
    as a cross-check on a gate array built some other way (e.g. spiral/point
    patterns that are gated on by construction).
    """
    xs, ys = xy_waveform[0, :], xy_waveform[1, :]
    inside = np.zeros(xs.shape, dtype=bool)
    for polygon in polygons:
        inside |= _points_in_polygon(polygon, xs, ys)
    return inside


def generate_stim_waveform(
    rois,
    sample_rate,
    n_samples,
    pattern="raster",
    spacing=0.05,
    dwell_time=0.001,
    transit_time=0.0002,
    revolutions=3,
):
    """Build one continuous, loopable (xy[2, n_samples], gate[n_samples])
    buffer scanning through all given ROIs in sequence, tiled/truncated to
    exactly fill an AO buffer of length `n_samples`.

    Parameters
    ----------
    rois : list
        For pattern="raster": a list of (M, 2) polygons (x, y galvo-voltage
        vertices). For pattern="spiral": a list of (center, radius) tuples.
    sample_rate : float
        Samples per second of the AO output.
    spacing : float
        Distance (volts) between adjacent raster points / spiral turns.
    dwell_time, transit_time : float
        Seconds to dwell at / transit to each point (raster pattern only).
    """
    if not rois:
        raise ValueError("rois must be non-empty.")

    dwell_samples = max(1, round(dwell_time * sample_rate))
    transit_samples = max(0, round(transit_time * sample_rate))

    xy_segments, gate_segments = [], []
    for roi in rois:
        if pattern == "raster":
            xy, gate = raster_fill_waveform(
                roi, spacing, dwell_samples, transit_samples
            )
        elif pattern == "spiral":
            center, radius = roi
            n_points = max(8, round(2 * np.pi * radius / spacing) * revolutions)
            xy, gate = spiral_waveform(center, radius, n_points, revolutions)
        else:
            raise ValueError(f"Unknown pattern {pattern!r}.")
        xy_segments.append(xy)
        gate_segments.append(gate)

    xy_all = np.concatenate(xy_segments, axis=1)
    gate_all = np.concatenate(gate_segments)

    reps = int(np.ceil(n_samples / xy_all.shape[1]))
    xy_tiled = np.tile(xy_all, reps)[:, :n_samples]
    gate_tiled = np.tile(gate_all, reps)[:n_samples]
    return xy_tiled, gate_tiled
