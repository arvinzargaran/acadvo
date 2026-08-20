/**
 * A section header, set as a platform sign: line bullet, station name in
 * expanded signage caps, and a rule running out to the edge of the measure.
 *
 * The bullet carries a letter as well as a colour. That is how real networks
 * name lines, and it is also the reason the page stays readable to someone who
 * can't separate the red line from the green one.
 */

/**
 * Only the three product areas are lines — degree planning, co-op, and the
 * advisor. Everything else on the page is an ordinary stop, and gets the plain
 * marker rather than borrowing a line's colour for decoration.
 */
const LINES = {
  C: { className: 'wf-bullet-c', label: 'Line C, degree' },
  W: { className: 'wf-bullet-w', label: 'Line W, work' },
  A: { className: 'wf-bullet-live', label: 'Line A, advisor' },
};

export default function StationSign({ line, name, note, className = '' }) {
  const spec = LINES[line];

  return (
    <div className={className}>
      <div className="wf-sign">
        {spec ? (
          <span className={`wf-bullet ${spec.className}`} aria-hidden="true">
            {line}
          </span>
        ) : (
          <span
            aria-hidden="true"
            className="flex-shrink-0 rounded-full"
            style={{
              width: '0.85rem',
              height: '0.85rem',
              background: 'var(--wf-canvas)',
              boxShadow: '0 0 0 3px var(--wf-ink)',
            }}
          />
        )}
        <h2
          className="wf-signage text-sm sm:text-base whitespace-nowrap"
          style={{ color: 'var(--wf-ink)' }}
        >
          {spec ? <span className="sr-only">{spec.label} — </span> : null}
          {name}
        </h2>
      </div>
      {note ? (
        <p className="mt-3 text-sm" style={{ color: 'var(--wf-muted)' }}>
          {note}
        </p>
      ) : null}
    </div>
  );
}
