import { useEffect, useMemo, useRef, useState } from 'react';
import { COURSES, analyse, chainFrom, layout } from './network';
import { trackPath } from './octolinear';

/**
 * The hero: a degree drawn as a transit network.
 *
 * Stations are courses, track is prerequisites, and the red line is the
 * critical path — the longest prerequisite chain, which is the thing that
 * actually decides whether you graduate on time. Interchanges (courses that
 * more than one later course depends on) get the double-ring marker a real map
 * gives a station where lines meet, because that is exactly what they are:
 * miss one and several routes close at once.
 */

const GEOM = { colGap: 190, rowGap: 78, padX: 74, padY: 56 };
const HEADER_H = 52; // room above the network for the term strip
const TERM_LABELS = ['FALL 1', 'WINTER 1', 'FALL 2', 'WINTER 2', 'FALL 3', 'WINTER 3'];

export default function RouteMap() {
  const analysis = useMemo(() => analyse(COURSES), []);
  const { nodes, edges, width, height, terms } = useMemo(
    () => layout(analysis, GEOM),
    [analysis],
  );
  const { dependents, critical, criticalLength, byId } = analysis;

  const [drawn, setDrawn] = useState(false);
  const [hovered, setHovered] = useState(null);
  const ref = useRef(null);

  // Draw the network in once it is actually on screen.
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDrawn(true);
      return undefined;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setDrawn(true);
          io.disconnect();
        }
      },
      { rootMargin: '-40px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const focus = hovered ? chainFrom(hovered, COURSES, dependents) : null;
  const nodeDim = (id) => (focus && !focus.has(id) ? 0.16 : 1);
  const edgeDim = (e) => (focus && !(focus.has(e.from) && focus.has(e.to)) ? 0.1 : 1);

  const totalH = height + HEADER_H;
  const hoveredCourse = hovered ? byId.get(hovered) : null;

  return (
    <div ref={ref} className="w-full">
      {/* The map scrolls sideways rather than shrinking to illegibility on a
          phone — which is how you read a real network map on a platform. */}
      <div className="overflow-x-auto overflow-y-hidden scrollbar-hide -mx-6 px-6 sm:mx-0 sm:px-0">
        <svg
          viewBox={`0 0 ${width} ${totalH}`}
          className="h-auto min-w-[860px] w-full"
          role="img"
          aria-label={
            `A computer science degree drawn as a transit map: ${COURSES.length} courses `
            + `across ${terms} terms. The red line is the critical path, `
            + `${criticalLength} terms long.`
          }
        >
          {/* ---- Term strip ---- */}
          {Array.from({ length: terms }).map((_, i) => {
            const x = GEOM.padX + i * GEOM.colGap;
            return (
              <g key={TERM_LABELS[i]}>
                <text
                  x={x}
                  y={20}
                  textAnchor="middle"
                  className="wf-signage"
                  fontSize="11"
                  fill="var(--wf-muted)"
                >
                  {TERM_LABELS[i]}
                </text>
                <line
                  x1={x}
                  y1={32}
                  x2={x}
                  y2={totalH - 12}
                  stroke="var(--wf-rule)"
                  strokeWidth="1"
                  strokeDasharray="2 6"
                />
              </g>
            );
          })}

          <g transform={`translate(0 ${HEADER_H})`}>
            {/* ---- Track ---- */}
            {edges.map((e, i) => (
              <path
                key={e.key}
                d={trackPath(e.a, e.b, 9)}
                className={`wf-track-line wf-draw ${drawn ? 'is-drawn' : ''}`}
                pathLength="1"
                stroke={e.onCritical ? 'var(--wf-line-c)' : 'var(--wf-rule)'}
                strokeWidth={e.onCritical ? 9 : 5}
                opacity={edgeDim(e)}
                style={{
                  transitionDelay: `${i * 55}ms`,
                  transitionProperty: 'stroke-dashoffset, opacity',
                }}
              />
            ))}

            {/* ---- Stations ---- */}
            {nodes.map((n) => {
              const onLine = critical.has(n.id);
              const isInterchange = dependents.get(n.id).length > 1;
              const stroke = onLine ? 'var(--wf-line-c)' : 'var(--wf-muted)';

              return (
                <g
                  key={n.id}
                  transform={`translate(${n.x} ${n.y})`}
                  opacity={drawn ? nodeDim(n.id) : 0}
                  style={{
                    transition: `opacity 380ms ease ${drawn ? 300 + n.col * 110 : 0}ms`,
                    cursor: 'pointer',
                  }}
                  onMouseEnter={() => setHovered(n.id)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(n.id)}
                  onBlur={() => setHovered(null)}
                  tabIndex={0}
                  role="listitem"
                  aria-label={`${n.id} ${n.name}${onLine ? ', on the critical path' : ''}`}
                >
                  {/* Interchange = a course more than one later course depends
                      on, drawn with the double ring a real map gives a station
                      where lines meet. Every other stop is a plain tick. */}
                  {isInterchange ? (
                    <>
                      <circle r="13" fill="var(--wf-canvas)" stroke={stroke} strokeWidth="4" />
                      <circle r="4.5" fill={stroke} />
                    </>
                  ) : (
                    <circle r="9" fill="var(--wf-canvas)" stroke={stroke} strokeWidth="4" />
                  )}

                  <text
                    y={isInterchange ? -24 : -20}
                    textAnchor="middle"
                    className="wf-code"
                    fontSize="13"
                    fontWeight="600"
                    fill={onLine ? 'var(--wf-line-c-text)' : 'var(--wf-ink)'}
                  >
                    {n.id}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* ---- Legend / readout ----
          Doubles as the hover readout, so the map never needs a tooltip that a
          keyboard or touch user can't reach. */}
      <div className="mt-6 flex flex-wrap items-center gap-x-7 gap-y-3 text-sm">
        <span className="flex items-center gap-2.5">
          <span className="wf-bullet wf-bullet-c">C</span>
          <span className="wf-signage text-[11px]" style={{ color: 'var(--wf-ink)' }}>
            Critical path · {criticalLength} terms
          </span>
        </span>
        <span className="flex items-center gap-2.5">
          <svg width="26" height="26" aria-hidden="true" className="flex-shrink-0">
            <circle cx="13" cy="13" r="9" fill="var(--wf-canvas)" stroke="var(--wf-muted)" strokeWidth="3" />
            <circle cx="13" cy="13" r="3.5" fill="var(--wf-muted)" />
          </svg>
          <span className="wf-signage text-[11px]" style={{ color: 'var(--wf-muted)' }}>
            Interchange
          </span>
        </span>
        {/* Mono is reserved for course codes — the product's real vocabulary —
            so the surrounding prose stays on the signage face. */}
        <span className="text-[13px] min-w-0 truncate" style={{ color: 'var(--wf-muted)' }} aria-live="polite">
          {hoveredCourse ? (
            <>
              <span className="wf-code" style={{ color: 'var(--wf-ink)' }}>{hoveredCourse.id}</span>
              {` ${hoveredCourse.name} · unlocks ${focus.size - 1} course${focus.size === 2 ? '' : 's'}`}
            </>
          ) : (
            'Hover a station to trace its line'
          )}
        </span>
      </div>
    </div>
  );
}
