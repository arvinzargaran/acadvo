import Badge from '../ui/Badge';
import { milestoneStatusLabel } from '../../utils/labels';

const statusColors = {
  pending: 'gray',
  in_progress: 'yellow',
  complete: 'green',
  overdue: 'red',
};

// Milestones are stops on the project's line, so they are drawn the way a
// network map draws a station rather than with status icons: a filled disc is
// a stop you have called at, a hollow ring is one still ahead, and the
// half-filled ring is where you are now. Colour repeats the state the marker
// shape already carries, so the list stays readable without it.
const markers = {
  complete:    'bg-[var(--wf-line-w)] border-[var(--wf-line-w)]',
  in_progress: 'bg-[var(--wf-canvas)] border-[var(--wf-live)] shadow-[inset_0_-4px_0_0_var(--wf-live)]',
  overdue:     'bg-[var(--wf-line-c)] border-[var(--wf-line-c)]',
  pending:     'bg-[var(--wf-canvas)] border-[var(--wf-rule)]',
};

export default function MilestoneList({ milestones, onUpdate }) {
  const sorted = [...milestones].sort((a, b) => a.order_index - b.order_index);

  const cycleStatus = (milestone) => {
    const order = ['pending', 'in_progress', 'complete'];
    const current = order.indexOf(milestone.status);
    const next = order[(current + 1) % order.length];
    onUpdate(milestone.id, { status: next });
  };

  return (
    <div>
      <p className="eyebrow mb-1.5">Milestones</p>
      {/* The track runs behind the markers and stops short of the last one, so
          the line reads as a route with an end rather than a divider. */}
      <ol className="relative">
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-4 top-5 bottom-5 w-[2px] bg-[var(--wf-rule)]"
        />
        {sorted.map(m => (
          <li key={m.id}>
            <button
              type="button"
              onClick={() => cycleStatus(m)}
              className="relative flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition-colors hover:bg-dark-700/60"
            >
              <span className="flex min-w-0 items-center gap-3">
                <span
                  aria-hidden="true"
                  className={`h-2.5 w-2.5 shrink-0 rounded-full border-2 ${markers[m.status] || markers.pending}`}
                />
                <span className={`truncate text-sm ${m.status === 'complete' ? 'text-dark-400 line-through' : 'text-dark-50'}`}>
                  {m.title}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                {m.target_date && (
                  <span className="wf-num text-xs text-dark-400">{m.target_date}</span>
                )}
                {/* The marker already carries the state, so the badge drops its
                    redundant dot and reads as the written-out label. */}
                <Badge color={statusColors[m.status]} variant="label">
                  {milestoneStatusLabel(m.status)}
                </Badge>
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
