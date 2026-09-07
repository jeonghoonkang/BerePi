"""Extract UV-grid face geometry and a face-adjacency graph from CAD B-reps."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np

from .features import CURVE_TYPES, FACE_SCALAR_DIM, SURFACE_TYPES, one_hot


def _occ():
    """Import OpenCascade lazily so cached datasets can train without OCC."""
    try:
        from OCC.Core import BRep, BRepAdaptor, BRepGProp, BRepLProp, GProp, IFSelect
        from OCC.Core import BRepTools, IGESControl, STEPControl, TopAbs, TopExp, TopTools, TopoDS
    except ImportError as exc:
        raise RuntimeError(
            "pythonocc-core is required for CAD preprocessing. "
            "Install it with: conda env create -f environment.yml"
        ) from exc
    return locals()


def load_shape(path: Path):
    occ = _occ()
    suffix = path.suffix.lower()
    if suffix in {".step", ".stp"}:
        reader = occ["STEPControl"].STEPControl_Reader()
        status = reader.ReadFile(str(path))
        if status != occ["IFSelect"].IFSelect_RetDone:
            raise ValueError(f"Failed to read STEP file: {path}")
        reader.TransferRoots()
        return reader.OneShape()
    if suffix in {".iges", ".igs"}:
        reader = occ["IGESControl"].IGESControl_Reader()
        status = reader.ReadFile(str(path))
        if status != occ["IFSelect"].IFSelect_RetDone:
            raise ValueError(f"Failed to read IGES file: {path}")
        reader.TransferRoots()
        return reader.OneShape()
    if suffix in {".brep", ".brp"}:
        shape = occ["TopoDS"].TopoDS_Shape()
        builder = occ["BRep"].BRep_Builder()
        if not occ["BRepTools"].breptools.Read(shape, str(path), builder):
            raise ValueError(f"Failed to read BREP file: {path}")
        return shape
    raise ValueError(f"Unsupported CAD extension: {suffix}; use STEP, IGES, or BREP")


def _surface_name(surface_type: int) -> str:
    # GeomAbs_SurfaceType enum values are stable in OpenCascade.
    return {0: "plane", 1: "cylinder", 2: "cone", 3: "sphere", 4: "torus",
            5: "bezier", 6: "bspline"}.get(int(surface_type), "other")


def _curve_name(curve_type: int) -> str:
    return {0: "line", 1: "circle", 2: "ellipse", 3: "hyperbola", 4: "parabola",
            5: "bezier", 6: "bspline"}.get(int(curve_type), "other")


def _mass(shape, kind: str) -> float:
    occ = _occ()
    props = occ["GProp"].GProp_GProps()
    if kind == "area":
        occ["BRepGProp"].brepgprop.SurfaceProperties(shape, props)
    else:
        occ["BRepGProp"].brepgprop.LinearProperties(shape, props)
    return float(props.Mass())


def _faces_and_edge_map(shape):
    occ = _occ()
    faces = []
    explorer = occ["TopExp"].TopExp_Explorer(shape, occ["TopAbs"].TopAbs_FACE)
    while explorer.More():
        faces.append(occ["TopoDS"].topods.Face(explorer.Current()))
        explorer.Next()
    indexed_faces = occ["TopTools"].TopTools_IndexedMapOfShape()
    occ["TopExp"].topexp.MapShapes(shape, occ["TopAbs"].TopAbs_FACE, indexed_faces)
    edge_faces = occ["TopTools"].TopTools_IndexedDataMapOfShapeListOfShape()
    occ["TopExp"].topexp.MapShapesAndAncestors(
        shape, occ["TopAbs"].TopAbs_EDGE, occ["TopAbs"].TopAbs_FACE, edge_faces
    )
    return faces, indexed_faces, edge_faces


def extract_brep(path: Path, resolution: int = 10) -> dict[str, np.ndarray]:
    occ = _occ()
    shape = load_shape(path)
    faces, indexed_faces, edge_faces = _faces_and_edge_map(shape)
    if not faces:
        raise ValueError(f"No B-rep faces found in {path}")

    areas = np.asarray([_mass(f, "area") for f in faces], dtype=np.float32)
    total_area = max(float(areas.sum()), 1e-12)
    # Translation/scale normalization preserves shape while handling CAD units.
    all_points: list[np.ndarray] = []
    raw_grids: list[np.ndarray] = []
    scalar_features: list[list[float]] = []

    for face, area in zip(faces, areas):
        adaptor = occ["BRepAdaptor"].BRepAdaptor_Surface(face, True)
        u0, u1, v0, v1 = map(float, (adaptor.FirstUParameter(), adaptor.LastUParameter(),
                                      adaptor.FirstVParameter(), adaptor.LastVParameter()))
        # Avoid sampling exactly on singular/trim boundaries.
        us = np.linspace(u0, u1, resolution + 2)[1:-1]
        vs = np.linspace(v0, v1, resolution + 2)[1:-1]
        grid = np.zeros((9, resolution, resolution), dtype=np.float32)
        props = occ["BRepLProp"].BRepLProp_SLProps(adaptor, 2, 1e-6)
        reversed_face = face.Orientation() == occ["TopAbs"].TopAbs_REVERSED
        for i, u in enumerate(us):
            for j, v in enumerate(vs):
                try:
                    props.SetParameters(float(u), float(v))
                    p = props.Value()
                    xyz = np.asarray([p.X(), p.Y(), p.Z()], dtype=np.float32)
                    # Classifier ensures samples outside a trimmed face are masked.
                    from OCC.Core.BRepClass import BRepClass_FaceClassifier
                    from OCC.Core.gp import gp_Pnt2d
                    classifier = BRepClass_FaceClassifier(face, gp_Pnt2d(float(u), float(v)), 1e-7)
                    valid = classifier.State() in (occ["TopAbs"].TopAbs_IN, occ["TopAbs"].TopAbs_ON)
                    if not valid or not props.IsNormalDefined():
                        continue
                    n = props.Normal()
                    sign = -1.0 if reversed_face else 1.0
                    grid[0:3, i, j] = xyz
                    grid[3:6, i, j] = sign * np.asarray([n.X(), n.Y(), n.Z()])
                    if props.IsCurvatureDefined():
                        k1, k2 = float(props.MaxCurvature()), float(props.MinCurvature())
                        grid[6, i, j], grid[7, i, j] = k1 * k2, 0.5 * (k1 + k2)
                    grid[8, i, j] = 1.0
                    all_points.append(xyz)
                except RuntimeError:
                    continue
        raw_grids.append(grid)
        stype = _surface_name(adaptor.GetType())
        scalar_features.append([
            math.log1p(float(area)), float(area) / total_area,
            math.log1p(abs(u1 - u0)), math.log1p(abs(v1 - v0)),
            *one_hot(stype, SURFACE_TYPES),
            float(adaptor.IsURational() or adaptor.IsVRational()),
            float(adaptor.IsUPeriodic()), float(adaptor.IsVPeriodic()),
        ])

    valid_points = np.stack(all_points) if all_points else np.zeros((1, 3), dtype=np.float32)
    center = valid_points.mean(0)
    scale = max(float(np.linalg.norm(valid_points - center, axis=1).max()), 1e-9)
    for grid in raw_grids:
        mask = grid[8] > 0
        grid[0:3, mask] = (grid[0:3, mask] - center[:, None]) / scale
        # Curvatures transform inversely with scale; make them unit-independent.
        grid[6, mask] *= scale * scale
        grid[7, mask] *= scale

    src, dst, edge_attr = [], [], []
    for edge_index in range(1, edge_faces.Extent() + 1):
        edge = occ["TopoDS"].topods.Edge(edge_faces.FindKey(edge_index))
        face_list = edge_faces.FindFromIndex(edge_index)
        adjacent = []
        iterator = occ["TopTools"].TopTools_ListIteratorOfListOfShape(face_list)
        while iterator.More():
            adjacent.append(iterator.Value())
            iterator.Next()
        if len(adjacent) != 2:  # boundary/non-manifold edges are not adjacency pairs
            continue
        a, b = indexed_faces.FindIndex(adjacent[0]) - 1, indexed_faces.FindIndex(adjacent[1]) - 1
        curve = occ["BRepAdaptor"].BRepAdaptor_Curve(edge)
        length = _mass(edge, "length")
        t = 0.5 * (float(curve.FirstParameter()) + float(curve.LastParameter()))
        # A robust signed-dihedral proxy using normals and edge tangent.
        cos_angle, sin_angle, convex, concave, smooth = 1.0, 0.0, 0.0, 0.0, 1.0
        try:
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.BRepLProp import BRepLProp_SLProps
            normals = []
            for f in adjacent:
                pcurve, first, last = BRep_Tool.CurveOnSurface(edge, f)
                uv = pcurve.Value(0.5 * (first + last))
                fp = BRepLProp_SLProps(occ["BRepAdaptor"].BRepAdaptor_Surface(f, True), uv.X(), uv.Y(), 1, 1e-6)
                n = fp.Normal()
                normals.append(np.asarray([n.X(), n.Y(), n.Z()]))
            tangent = curve.DN(t, 1)
            tangent = np.asarray([tangent.X(), tangent.Y(), tangent.Z()])
            tangent /= max(np.linalg.norm(tangent), 1e-12)
            cos_angle = float(np.clip(normals[0] @ normals[1], -1, 1))
            sin_angle = float(tangent @ np.cross(normals[0], normals[1]))
            smooth = float(abs(sin_angle) < 1e-3 and cos_angle > 0.999)
            convex, concave = float(sin_angle > 1e-3), float(sin_angle < -1e-3)
        except RuntimeError:
            pass
        attr = [math.log1p(length), length / max(math.sqrt(total_area), 1e-9),
                cos_angle, sin_angle, convex, concave, smooth,
                float(edge.Closed()), *one_hot(_curve_name(curve.GetType()), CURVE_TYPES)]
        for s, d in ((a, b), (b, a)):
            src.append(s); dst.append(d); edge_attr.append(attr)

    return {
        "face_uv": np.stack(raw_grids).astype(np.float32),
        "face_attr": np.asarray(scalar_features, dtype=np.float32),
        "edge_index": np.asarray([src, dst], dtype=np.int64).reshape(2, -1),
        "edge_attr": np.asarray(edge_attr, dtype=np.float32).reshape(-1, 16),
        "center": center.astype(np.float32), "scale": np.asarray(scale, dtype=np.float32),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--resolution", type=int, default=10)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in args.input_dir.rglob("*") if p.suffix.lower() in {".step", ".stp", ".iges", ".igs", ".brep", ".brp"})
    if not files:
        raise SystemExit(f"No STEP/IGES/BREP files found under {args.input_dir}")
    failures = []
    for path in files:
        try:
            relative = path.relative_to(args.input_dir).with_suffix(".npz")
            target = args.output_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(target, **extract_brep(path, args.resolution), source=str(path))
            print(f"[ok] {path} -> {target}")
        except Exception as exc:  # continue a large industrial batch and report failures
            failures.append((str(path), repr(exc)))
            print(f"[failed] {path}: {exc}")
    if failures:
        with (args.output_dir / "failures.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f); writer.writerow(["file", "error"]); writer.writerows(failures)
        print(f"Completed with {len(failures)} failures; see failures.csv")


if __name__ == "__main__":
    main()
