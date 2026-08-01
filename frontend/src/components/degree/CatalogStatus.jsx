import { useEffect, useState } from 'react';
import { getCatalogStatus } from '../../api/degree';
import Badge from '../ui/Badge';

// Format an ISO datetime into a short, human "updated {date}" string.
function formatDate(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

/**
 * "Verified vs best-effort" catalog badge.
 *
 * Surfaces whether AI advising is grounded in a real, seeded course catalog for
 * the student's university (green, "verified") or is running best-effort off
 * their own uploaded courses (amber). Fetches its own status on mount.
 */
export default function CatalogStatus() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getCatalogStatus()
      .then((res) => { if (active) setStatus(res.data); })
      .catch(() => { if (active) setStatus(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  if (loading) {
    return (
      <div className="bg-dark-800 border border-dark-700 rounded-xl px-4 py-3 animate-pulse">
        <div className="h-4 w-64 bg-dark-700 rounded" />
      </div>
    );
  }

  // No status at all (request failed) — stay quiet rather than mislead.
  if (!status) return null;

  const { university, verified, course_count, last_updated, sources } = status;
  const updated = formatDate(last_updated);

  if (verified) {
    return (
      <div
        className="flex items-start gap-3 bg-green-500/10 ring-1 ring-inset ring-green-500/25 rounded-xl px-4 py-3"
        role="status"
      >
        <span className="icon-chip flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg">
          <svg className="w-5 h-5 text-green-500 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </span>
        <div className="text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-display text-base text-dark-50">
              Verified catalog{university ? ` for ${university}` : ''}
            </p>
            <Badge color="green" variant="label" dot>Verified</Badge>
          </div>
          <p className="text-dark-300 mt-1">
            Advising is grounded in {course_count} verified course{course_count === 1 ? '' : 's'}
            {updated ? `, updated ${updated}` : ''}.
            {sources && sources.length > 0 ? ` Source: ${sources.join(', ')}.` : ''}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex items-start gap-3 bg-amber-500/10 ring-1 ring-inset ring-amber-500/25 rounded-xl px-4 py-3"
      role="status"
    >
      <span className="icon-chip flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg">
        <svg className="w-5 h-5 text-amber-500 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M4.93 19h14.14c1.54 0 2.5-1.67 1.73-3L13.73 4a2 2 0 00-3.46 0L3.2 16c-.77 1.33.19 3 1.73 3z" />
        </svg>
      </span>
      <div className="text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-display text-base text-dark-50">Best-effort mode</p>
          <Badge color="yellow" variant="label" dot>Unverified</Badge>
        </div>
        <p className="text-dark-300 mt-1">
          {university
            ? `No verified catalog for ${university} yet. `
            : ''}
          Advising is based on your uploaded courses — verify against your official calendar.
        </p>
      </div>
    </div>
  );
}
