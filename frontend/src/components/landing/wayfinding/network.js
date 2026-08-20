/**
 * The degree, as a network.
 *
 * A real York EECS prerequisite chain, trimmed to the courses that shape the
 * critical path. Edges point prerequisite → dependent. Nothing about the
 * layout is hand-placed: term columns come from each course's longest path
 * from a root, so an edge can never point backwards, and the red line is the
 * graph's true longest chain — the one that actually sets time-to-graduation,
 * because every course on it has to be taken in a separate term.
 */

export const COURSES = [
  { id: 'EECS 1012', name: 'Net-Centric Computing', prereqs: [] },
  { id: 'MATH 1013', name: 'Calculus I', prereqs: [] },
  { id: 'EECS 1021', name: 'Object-Oriented Prog.', prereqs: ['EECS 1012'] },
  { id: 'EECS 1019', name: 'Discrete Mathematics', prereqs: ['MATH 1013'] },
  { id: 'MATH 1014', name: 'Calculus II', prereqs: ['MATH 1013'] },
  { id: 'EECS 2030', name: 'Advanced OOP', prereqs: ['EECS 1021'] },
  { id: 'MATH 2030', name: 'Probability', prereqs: ['MATH 1014'] },
  { id: 'EECS 2011', name: 'Data Structures', prereqs: ['EECS 2030', 'EECS 1019'] },
  { id: 'EECS 2021', name: 'Computer Organization', prereqs: ['EECS 2030'] },
  { id: 'EECS 3101', name: 'Algorithm Design', prereqs: ['EECS 2011', 'EECS 1019'] },
  { id: 'EECS 3221', name: 'Operating Systems', prereqs: ['EECS 2011', 'EECS 2021'] },
  { id: 'EECS 3421', name: 'Databases', prereqs: ['EECS 2011'] },
  { id: 'EECS 4101', name: 'Advanced Data Structures', prereqs: ['EECS 3101'] },
  { id: 'EECS 4404', name: 'Machine Learning', prereqs: ['EECS 3101', 'MATH 2030'] },
];

/**
 * Kahn's algorithm for a topological order, then one forward pass for the
 * longest path into each node. `depth` doubles as the term index — a node
 * always sits to the right of every prerequisite — and `from` lets us walk the
 * critical path back from the deepest node.
 */
export function analyse(courses = COURSES) {
  const byId = new Map(courses.map((c) => [c.id, c]));
  const dependents = new Map(courses.map((c) => [c.id, []]));
  const indegree = new Map(courses.map((c) => [c.id, 0]));

  courses.forEach((c) => {
    c.prereqs.forEach((p) => {
      dependents.get(p).push(c.id);
      indegree.set(c.id, indegree.get(c.id) + 1);
    });
  });

  const queue = courses.filter((c) => indegree.get(c.id) === 0).map((c) => c.id);
  const order = [];
  while (queue.length) {
    const id = queue.shift();
    order.push(id);
    dependents.get(id).forEach((d) => {
      indegree.set(d, indegree.get(d) - 1);
      if (indegree.get(d) === 0) queue.push(d);
    });
  }

  const depth = new Map(courses.map((c) => [c.id, 0]));
  const from = new Map();
  order.forEach((id) => {
    byId.get(id).prereqs.forEach((p) => {
      if (depth.get(p) + 1 > depth.get(id)) {
        depth.set(id, depth.get(p) + 1);
        from.set(id, p);
      }
    });
  });

  // Walk back from the deepest node to recover the longest chain.
  let tail = order[0];
  order.forEach((id) => {
    if (depth.get(id) > depth.get(tail)) tail = id;
  });
  const critical = [];
  for (let id = tail; id; id = from.get(id)) critical.unshift(id);

  return {
    order,
    depth,
    dependents,
    byId,
    critical: new Set(critical),
    criticalPath: critical,
    criticalLength: critical.length,
  };
}

/** Every course reachable from `id` in either direction — the chain it sits on. */
export function chainFrom(id, courses, dependents) {
  const byId = new Map(courses.map((c) => [c.id, c]));
  const seen = new Set([id]);
  const walk = (start, next) => {
    const stack = [start];
    while (stack.length) {
      const cur = stack.pop();
      next(cur).forEach((n) => {
        if (!seen.has(n)) {
          seen.add(n);
          stack.push(n);
        }
      });
    }
  };
  walk(id, (n) => dependents.get(n));
  walk(id, (n) => byId.get(n).prereqs);
  return seen;
}

/**
 * Term columns and row slots for every course, plus the octolinear-ready edge
 * list. Rows are assigned per column and centred, so the network reads as a
 * band rather than drifting off one edge.
 */
export function layout(analysis, geom) {
  const { depth, critical } = analysis;
  const { colGap, rowGap, padX, padY } = geom;

  const columns = new Map();
  COURSES.forEach((c) => {
    const d = depth.get(c.id);
    if (!columns.has(d)) columns.set(d, []);
    columns.get(d).push(c.id);
  });

  const maxRows = Math.max(...[...columns.values()].map((ids) => ids.length));
  const height = padY * 2 + (maxRows - 1) * rowGap;

  const pos = new Map();
  columns.forEach((ids, col) => {
    ids.forEach((id, row) => {
      pos.set(id, {
        x: padX + col * colGap,
        y: height / 2 + (row - (ids.length - 1) / 2) * rowGap,
      });
    });
  });

  const edges = COURSES.flatMap((c) =>
    c.prereqs.map((p) => ({
      key: `${p}->${c.id}`,
      from: p,
      to: c.id,
      a: pos.get(p),
      b: pos.get(c.id),
      onCritical: critical.has(p) && critical.has(c.id),
    })),
  );

  // Critical-path track is drawn last so it sits over the branch lines.
  edges.sort((x, y) => Number(x.onCritical) - Number(y.onCritical));

  return {
    nodes: COURSES.map((c) => ({ ...c, ...pos.get(c.id), col: depth.get(c.id) })),
    edges,
    width: padX * 2 + (columns.size - 1) * colGap,
    height,
    terms: columns.size,
  };
}
