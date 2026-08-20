/**
 * Octolinear geometry — the grammar that makes a diagram read as a transit map.
 *
 * Real network maps (Beck's Underground and every descendant) allow track to
 * run at only four angles: horizontal, vertical, and the two 45° diagonals.
 * That constraint is the whole look. Curved or free-angle connectors read as a
 * flowchart instead, which is what most generated "dependency graphs" are.
 */

/** Trim `r` back along `from → to` and return the point. */
function towards(from, to, r) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.hypot(dx, dy);
  if (len === 0) return { ...from };
  const t = Math.min(r, len / 2) / len;
  return { x: from.x + dx * t, y: from.y + dy * t };
}

/**
 * An SVG path through `points` with each interior corner rounded to `radius`.
 * The corner is cut back along both incident segments and bridged with a
 * quadratic whose control point is the original vertex, so the fillet stays
 * tangent to both runs whatever the angle between them.
 */
export function roundedPath(points, radius = 10) {
  if (points.length < 2) return '';
  if (points.length === 2) {
    return `M${points[0].x},${points[0].y} L${points[1].x},${points[1].y}`;
  }

  let d = `M${points[0].x},${points[0].y}`;
  for (let i = 1; i < points.length - 1; i += 1) {
    const prev = points[i - 1];
    const cur = points[i];
    const next = points[i + 1];

    // Clamp so two tight corners on a short run can't overshoot each other.
    const r = Math.min(
      radius,
      Math.hypot(cur.x - prev.x, cur.y - prev.y) / 2,
      Math.hypot(next.x - cur.x, next.y - cur.y) / 2,
    );

    const enter = towards(cur, prev, r);
    const exit = towards(cur, next, r);
    d += ` L${enter.x},${enter.y} Q${cur.x},${cur.y} ${exit.x},${exit.y}`;
  }

  const last = points[points.length - 1];
  return `${d} L${last.x},${last.y}`;
}

/**
 * Waypoints for a left-to-right connection between two stations, using only
 * straight and 45° runs.
 *
 * With enough horizontal room the track runs flat, takes a single diagonal to
 * change row, then flattens again. When the row change is taller than the gap
 * is wide, the diagonal can't absorb it, so the run goes vertical first
 * instead and the diagonal covers the full horizontal distance.
 */
export function octolinearRoute(a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;

  if (dy === 0 || dx === 0) return [a, b];

  const adx = Math.abs(dx);
  const ady = Math.abs(dy);
  const sx = Math.sign(dx);
  const sy = Math.sign(dy);

  if (adx >= ady) {
    // Flat → 45° → flat. The diagonal consumes `ady` of the horizontal budget.
    const run = (adx - ady) / 2;
    return [
      a,
      { x: a.x + sx * run, y: a.y },
      { x: a.x + sx * (run + ady), y: b.y },
      b,
    ];
  }

  // Vertical → 45° → vertical.
  const run = (ady - adx) / 2;
  return [
    a,
    { x: a.x, y: a.y + sy * run },
    { x: b.x, y: a.y + sy * (run + adx) },
    b,
  ];
}

/** Convenience: a finished, corner-rounded octolinear path between two points. */
export function trackPath(a, b, radius = 10) {
  return roundedPath(octolinearRoute(a, b), radius);
}
