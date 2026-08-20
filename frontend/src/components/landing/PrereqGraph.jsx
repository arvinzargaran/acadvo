import { useEffect, useMemo, useRef, useState } from 'react';
import { COURSES, analyse } from './wayfinding/network';

/**
 * The critical path, drawn as a carriage strip diagram.
 *
 * The hero map shows the whole network; this shows the one line that decides
 * the graduation date, straightened out the way the diagram above a train door
 * straightens a route. Every station on it has to be taken in a separate term,
 * which is the whole point: slip one and the degree slips with it.
 *
 * The chain is computed, not authored — it is the longest path through the
 * real prerequisite graph.
 */

// Wide enough that the first and last course codes, which are centred on their
// stations, stay inside the viewBox instead of being clipped at the edges.
const PAD_X = 62;
const LINE_Y = 96;
const VIEW_H = 168;
const STEP = 104;

export default function PrereqGraph() {
  const { criticalPath, byId } = useMemo(() => analyse(COURSES), []);
  const [drawn, setDrawn] = useState(false);
  const [active, setActive] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDrawn(true);
      return undefined;
    }
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setDrawn(true);
          io.disconnect();
        }
      },
      { rootMargin: '-40px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const width = PAD_X * 2 + (criticalPath.length - 1) * STEP;
  const x = (i) => PAD_X + i * STEP;
  const activeCourse = active ? byId.get(active) : null;

  return (
    <div ref={ref} className="wf-raised">
      <div
        className="flex items-center gap-2.5 px-4 py-3"
        style={{ borderBottom: '1px solid var(--wf-rule)' }}
      >
        <span
          className="wf-bullet wf-bullet-c"
          style={{ width: '1.1rem', height: '1.1rem', fontSize: '0.625rem' }}
          aria-hidden="true"
        >
          C
        </span>
        <span className="wf-signage text-[10px]" style={{ color: 'var(--wf-muted)' }}>
          Critical path
        </span>
        <span className="wf-signage text-[10px] ml-auto" style={{ color: 'var(--wf-line-c-text)' }}>
          {criticalPath.length} terms
        </span>
      </div>

      <div className="overflow-x-auto scrollbar-hide px-4 py-2">
        <svg
          viewBox={`0 0 ${width} ${VIEW_H}`}
          className="h-auto w-full min-w-[420px]"
          role="img"
          aria-label={`The critical path runs ${criticalPath.length} terms: ${criticalPath.join(', ')}.`}
        >
          {/* Track */}
          <line
            x1={x(0)}
            y1={LINE_Y}
            x2={x(criticalPath.length - 1)}
            y2={LINE_Y}
            className={`wf-track-line wf-draw ${drawn ? 'is-drawn' : ''}`}
            pathLength="1"
            stroke="var(--wf-line-c)"
            strokeWidth="8"
          />

          {criticalPath.map((id, i) => {
            const course = byId.get(id);
            const isActive = active === id;
            return (
              <g
                key={id}
                transform={`translate(${x(i)} 0)`}
                opacity={drawn ? 1 : 0}
                style={{
                  transition: `opacity 320ms ease ${drawn ? 250 + i * 110 : 0}ms`,
                  cursor: 'pointer',
                }}
                onMouseEnter={() => setActive(id)}
                onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(id)}
                onBlur={() => setActive(null)}
                tabIndex={0}
                aria-label={`${id} ${course.name}, term ${i + 1}`}
              >
                <circle
                  cy={LINE_Y}
                  r={isActive ? 11 : 9}
                  fill="var(--wf-canvas)"
                  stroke="var(--wf-line-c)"
                  strokeWidth="4"
                  style={{ transition: 'r 160ms ease' }}
                />
                {/* Codes stagger above and below so six of them fit without
                    colliding — the same trick a dense strip map uses. */}
                <text
                  y={i % 2 === 0 ? LINE_Y - 26 : LINE_Y + 34}
                  textAnchor="middle"
                  className="wf-code"
                  fontSize="15"
                  fontWeight="600"
                  fill="var(--wf-ink)"
                >
                  {id}
                </text>
                <text
                  y={i % 2 === 0 ? LINE_Y - 44 : LINE_Y + 50}
                  textAnchor="middle"
                  className="wf-signage"
                  fontSize="11"
                  fill="var(--wf-muted)"
                >
                  {`TERM ${i + 1}`}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="px-4 py-3" style={{ borderTop: '1px solid var(--wf-rule)' }}>
        <p className="wf-code text-[12px] truncate" style={{ color: 'var(--wf-muted)' }} aria-live="polite">
          {activeCourse
            ? `${activeCourse.id} — ${activeCourse.name}`
            : 'Six terms back to back. Miss one and graduation moves.'}
        </p>
      </div>
    </div>
  );
}
