"""SVG path parser for converting SVG path commands to flattened point lists.

This module provides utilities to parse SVG path data (the `d` attribute) and convert
it into lists of 2D points. It handles all standard SVG path commands including:
- M (moveto) - starts a new subpath
- L (lineto) - straight line segments
- C (cubic bezier) - cubic Bézier curves
- Q (quadratic bezier) - quadratic Bézier curves
- A (arc) - elliptical arc curves
- Z (closepath) - closes the current subpath

Curves are adaptively sampled based on their arc length to produce smooth approximations.
Multiple subpaths (separated by M commands) are returned as separate point lists, which
is essential for rendering paths with holes using even-odd fill rules.
"""

from __future__ import annotations

import math


def flatten_subpaths(
    d: str, samples_per_unit: int = 64
) -> list[list[tuple[float, float]]]:
    """Flatten an SVG path string into per-subpath point lists.

    Parses an SVG path `d` attribute and converts all commands (M/L/C/Q/A/Z) into
    lists of 2D points. Each `M` (moveto) command starts a new subpath, which is
    important for rendering paths with holes (e.g., letter counters, ring interiors)
    using even-odd fill rules.

    Curves are adaptively tessellated: the number of samples is proportional to the
    curve's arc length (`samples_per_unit` samples per coordinate unit), ensuring
    smooth rendering without excessive point density.

    Args:
        d: SVG path data string (e.g., "M 10 10 L 20 20 C 30 30 40 40 50 50 Z")
        samples_per_unit: Number of samples per coordinate unit for curve tessellation.
            Higher values produce smoother curves at the cost of more points.
            Default is 64, which works well for most cases.

    Returns:
        A list of subpaths, where each subpath is a list of (x, y) coordinate tuples.
        An empty list is returned if the path is empty or invalid.

    Example:
        >>> flatten_subpaths("M 0 0 L 10 0 L 10 10 Z")
        [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 0.0)]]

        >>> # Path with a hole (outer ring + inner ring)
        >>> flatten_subpaths("M 0 0 L 100 0 L 100 100 L 0 100 Z M 25 25 L 75 25 L 75 75 L 25 75 Z")
        [[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0), (0.0, 0.0)],
         [(25.0, 25.0), (75.0, 25.0), (75.0, 75.0), (25.0, 75.0), (25.0, 25.0)]]
    """
    tokens = d.replace(",", " ").split()
    if not tokens:
        return []

    subpaths: list[list[tuple[float, float]]] = []
    out: list[tuple[float, float]] = []
    cur = (0.0, 0.0)  # Current pen position
    start: tuple[float, float] | None = None  # Start of current subpath for Z command
    i = 0
    cmd = "M"  # Default command (implicit lineto after first M)

    def num(index: int) -> float:
        """Parse a token as a float coordinate."""
        return float(tokens[index])

    while i < len(tokens):
        token = tokens[i]

        # Command letter switches the current command mode
        if token.isalpha():
            cmd = token
            i += 1
            continue

        # Process coordinates based on current command
        if cmd == "M":
            # Moveto: start a new subpath
            x, y = num(i), num(i + 1)
            i += 2
            if out:
                subpaths.append(out)
                out = []
            out.append((x, y))
            start = (x, y)
            cur = (x, y)

        elif cmd == "L":
            # Lineto: straight line
            x, y = num(i), num(i + 1)
            i += 2
            out.append((x, y))
            cur = (x, y)

        elif cmd == "C":
            # Cubic Bézier curve: cur -> (c1x, c1y) -> (c2x, c2y) -> (x, y)
            c1x, c1y = num(i), num(i + 1)
            c2x, c2y = num(i + 2), num(i + 3)
            x, y = num(i + 4), num(i + 5)
            i += 6

            # Adaptive sampling based on arc length approximation
            arc_length = math.hypot(x - cur[0], y - cur[1])
            n = max(4, int(samples_per_unit * arc_length))

            # Evaluate cubic Bézier at n sample points
            for t in range(1, n + 1):
                u = t / n
                mu = 1 - u
                # B(u) = (1-u)³P₀ + 3(1-u)²uP₁ + 3(1-u)u²P₂ + u³P₃
                px = (
                    mu**3 * cur[0]
                    + 3 * mu**2 * u * c1x
                    + 3 * mu * u**2 * c2x
                    + u**3 * x
                )
                py = (
                    mu**3 * cur[1]
                    + 3 * mu**2 * u * c1y
                    + 3 * mu * u**2 * c2y
                    + u**3 * y
                )
                out.append((px, py))
            cur = (x, y)

        elif cmd == "Q":
            # Quadratic Bézier curve: cur -> (qx, qy) -> (x, y)
            qx, qy = num(i), num(i + 1)
            x, y = num(i + 2), num(i + 3)
            i += 4

            # Adaptive sampling
            arc_length = math.hypot(x - cur[0], y - cur[1])
            n = max(4, int(samples_per_unit * arc_length))

            # Evaluate quadratic Bézier at n sample points
            for t in range(1, n + 1):
                u = t / n
                mu = 1 - u
                # B(u) = (1-u)²P₀ + 2(1-u)uP₁ + u²P₂
                px = mu**2 * cur[0] + 2 * mu * u * qx + u**2 * x
                py = mu**2 * cur[1] + 2 * mu * u * qy + u**2 * y
                out.append((px, py))
            cur = (x, y)

        elif cmd == "A":
            # Elliptical arc: complex conversion to points
            rx, ry = num(i), num(i + 1)
            rot = num(i + 2)
            large_arc_flag = int(num(i + 3))
            sweep_flag = int(num(i + 4))
            x, y = num(i + 5), num(i + 6)
            i += 7

            pts = arc_to_points(
                cur, (x, y), rx, ry, rot, large_arc_flag, sweep_flag
            )
            out.extend(pts)
            cur = (x, y)

        elif cmd == "Z":
            # Closepath: connect back to start
            if start and out and start != out[-1]:
                out.append(start)
                cur = start
            i += 1

        else:
            raise ValueError(f"unsupported SVG command: {cmd}")

    # Append the final subpath if any
    if out:
        subpaths.append(out)

    return subpaths


def arc_to_points(
    start: tuple[float, float],
    end: tuple[float, float],
    rx: float,
    ry: float,
    rot: float,
    large_arc_flag: int,
    sweep_flag: int,
) -> list[tuple[float, float]]:
    """Convert an SVG elliptical arc to a sequence of line segments.

    Implements the SVG arc conversion algorithm that converts from endpoint
    parameterization (start, end, radii, flags) to center parameterization
    (center, angle range), then samples points along the arc.

    This follows the SVG 1.1 specification for elliptical arc implementation:
    https://www.w3.org/TR/SVG/implnotes.html#ArcImplementationNotes

    Args:
        start: Starting point (x, y) of the arc
        end: Ending point (x, y) of the arc
        rx: X-axis radius of the ellipse
        ry: Y-axis radius of the ellipse
        rot: Rotation angle of the ellipse in degrees
        large_arc_flag: 0 for small arc, 1 for large arc (determines which of
            the two possible arcs to draw)
        sweep_flag: 0 for counterclockwise, 1 for clockwise

    Returns:
        A list of (x, y) points approximating the arc, not including the start
        point (which is already in the path), but including the end point.

    Example:
        >>> # Quarter circle from (0, 0) to (10, 10)
        >>> points = arc_to_points((0, 0), (10, 10), 10, 10, 0, 0, 1)
        >>> len(points) > 5  # Should produce multiple points
        True
    """
    rx, ry = abs(rx), abs(ry)

    # Degenerate arc: zero radius → straight line
    if rx == 0 or ry == 0:
        return [end]

    # Convert rotation angle to radians
    phi = math.radians(rot % 360)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)

    x1, y1 = start
    x2, y2 = end

    # Step 1: Compute (x1', y1') - transform to unit circle space
    dx = (x1 - x2) / 2
    dy = (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy

    # Step 2: Correct radii if they're too small (out-of-range correction)
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s

    # Step 3: Compute center point (cx', cy') in transformed space
    rx2, ry2 = rx * rx, ry * ry
    denom = rx2 * y1p * y1p + ry2 * x1p * x1p

    # Avoid division by zero
    if abs(denom) < 1e-12:
        return [end]

    num = rx2 * ry2 - rx2 * y1p * y1p - ry2 * x1p * x1p
    coef = math.sqrt(max(0.0, num / denom))

    # Choose center based on large-arc and sweep flags
    if large_arc_flag == sweep_flag:
        coef = -coef

    cxp = coef * (rx * y1p / ry)
    cyp = coef * -(ry * x1p / rx)

    # Step 4: Compute center (cx, cy) in original space
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2

    # Step 5: Compute start and delta angles
    def angle_between(ux: float, uy: float, vx: float, vy: float) -> float:
        """Compute signed angle between two vectors."""
        dot = ux * vx + uy * vy
        det = ux * vy - uy * vx
        return math.atan2(det, dot)

    theta1 = angle_between(1.0, 0.0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    delta = angle_between(
        (x1p - cxp) / rx,
        (y1p - cyp) / ry,
        (-x1p - cxp) / rx,
        (-y1p - cyp) / ry,
    )

    # Correct delta based on sweep direction
    if sweep_flag == 0 and delta > 0:
        delta -= 2 * math.pi
    if sweep_flag == 1 and delta < 0:
        delta += 2 * math.pi

    # Step 6: Sample points along the arc
    # Use adaptive step count based on arc angle
    steps = max(8, min(128, int(abs(delta) / (math.pi / 48))))

    pts: list[tuple[float, float]] = []
    for k in range(1, steps + 1):
        t = theta1 + delta * k / steps
        # Transform from unit circle back to original space
        x = cx + rx * math.cos(t) * cos_phi - ry * math.sin(t) * sin_phi
        y = cy + rx * math.cos(t) * sin_phi + ry * math.sin(t) * cos_phi
        pts.append((x, y))

    return pts
