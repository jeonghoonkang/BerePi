"""Feature definitions shared by extraction, datasets, and models."""

from __future__ import annotations

SURFACE_TYPES = ("plane", "cylinder", "cone", "sphere", "torus", "bezier", "bspline", "other")
CURVE_TYPES = ("line", "circle", "ellipse", "hyperbola", "parabola", "bezier", "bspline", "other")

# Per UV sample: normalized xyz, unit normal, Gaussian/mean curvature, valid mask.
UV_CHANNELS = 9
# area, relative area, u/v span, surface one-hot, rational flag, periodic u/v.
FACE_SCALAR_DIM = 4 + len(SURFACE_TYPES) + 3
# length, relative length, dihedral cosine/sine, convex/concave/smooth flags,
# closed flag, curve one-hot.
EDGE_FEATURE_DIM = 2 + 2 + 3 + 1 + len(CURVE_TYPES)


def one_hot(name: str, values: tuple[str, ...]) -> list[float]:
    result = [0.0] * len(values)
    result[values.index(name if name in values else "other")] = 1.0
    return result
