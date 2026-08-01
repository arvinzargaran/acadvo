import { useMemo } from 'react';
import { getStyle, daysUntil, daysRemainingBadge } from './styles';

const MAJOR_TYPES = ['exam', 'milestone', 'deadline', 'co_op'];

function getSemester(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const month = d.getMonth(); // 0-indexed
  const year = d.getFullYear();
  if (month >= 0 && month <= 3) return { label: `Winter ${year}`, order: year * 10 + 1 };
  if (month >= 4 && month <= 7) return { label: `Summer ${year}`, order: year * 10 + 2 };
  return { label: `Fall ${year}`, order: year * 10 + 3 };
}

function isCurrent(semLabel) {
  const now = new Date();
  const { label } = getSemester(now.toISOString().split('T')[0]);
  return label === semLabel;
}

export default function YearlyView({ events }) {
  // Filter to major events only
  const majorEvents = useMemo(() => {
    return events.filter(e => {
      if (!e.date) return false;
      // Include exams, milestones, hard deadlines, co-op deadlines
      if (MAJOR_TYPES.includes(e.type)) return true;
      // Include career events (always strategic)
      if (e.category === 'career') return true;
      // Include project milestones
      if (e.category === 'project') return true;
      return false;
    });
  }, [events]);

  // Group by semester
  const semesters = useMemo(() => {
    const map = {};
    for (const e of majorEvents) {
      const sem = getSemester(e.date);
      if (!map[sem.label]) map[sem.label] = { label: sem.label, order: sem.order, events: [] };
      map[sem.label].events.push(e);
    }
    // Sort semesters chronologically
    return Object.values(map).sort((a, b) => a.order - b.order);
  }, [majorEvents]);

  if (semesters.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="icon-chip w-14 h-14 mx-auto mb-4 rounded-2xl flex items-center justify-center text-primary-600 dark:text-primary-400">
          <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
        </div>
        <p className="font-display text-xl text-dark-50">No milestones on the horizon</p>
        <p className="text-dark-400 text-sm mt-1">Upload syllabi or add career deadlines to see your strategic roadmap.</p>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Vertical spine */}
      <div className="absolute left-6 top-0 bottom-0 w-px bg-dark-700" />

      <div className="space-y-8">
        {semesters.map(sem => {
          const current = isCurrent(sem.label);
          return (
            <div key={sem.label} className="relative">
              {/* Semester header */}
              <div className="flex items-center gap-3 mb-4 relative z-10">
                <div className={`w-3 h-3 rounded-full border-2 ${
                  current ? 'border-primary-500 bg-primary-500 shadow-lg shadow-primary-500/30' : 'border-dark-400 bg-dark-800'
                }`} style={{ marginLeft: '18px' }} />
                <h3 className={`font-display text-lg ${current ? 'text-dark-50' : 'text-dark-300'}`}>
                  {sem.label}
                  {current && <span className="ml-2 text-xs text-primary-500 dark:text-primary-400 font-sans">(Current)</span>}
                </h3>
                <span className="text-dark-500 text-xs">{sem.events.length} event{sem.events.length !== 1 ? 's' : ''}</span>
              </div>

              {/* Events */}
              <div className="ml-14 space-y-2">
                {sem.events
                  .sort((a, b) => (a.date || '').localeCompare(b.date || ''))
                  .map(e => {
                    const s = getStyle(e.category);
                    const days = daysUntil(e.date);
                    const badge = daysRemainingBadge(days);
                    const dateLabel = new Date(e.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    return (
                      <div
                        key={e.id}
                        className={`flex items-center gap-4 rounded-xl border ${s.border} bg-dark-800 p-3 transition hover:bg-dark-700`}
                      >
                        {/* Date column */}
                        <div className="w-14 text-center flex-shrink-0">
                          <p className="text-dark-300 text-xs font-medium">{dateLabel}</p>
                        </div>

                        {/* Color bar */}
                        <div className={`w-1 h-10 rounded-full ${s.dot} flex-shrink-0`} />

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <p className="text-dark-50 text-sm font-medium truncate">{e.title}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className={`text-[10px] px-2 py-0.5 rounded-full border ${s.badge} capitalize`}>{e.category}</span>
                            <span className="text-dark-500 text-[10px]">{e.type}</span>
                          </div>
                        </div>

                        {/* Weight + days badge */}
                        <div className="flex flex-col items-end gap-1 flex-shrink-0">
                          {e.weight != null && (
                            <span className={`text-xs font-semibold ${s.text}`}>{e.weight}%</span>
                          )}
                          <span className={`text-[10px] px-2 py-0.5 rounded-full border whitespace-nowrap ${badge.cls}`}>{badge.label}</span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
