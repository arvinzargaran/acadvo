import { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router';
import { getSchedule } from '../api/schedule';
import WeeklyView from '../components/schedule/WeeklyView';
import MonthlyView from '../components/schedule/MonthlyView';
import YearlyView from '../components/schedule/YearlyView';
import { getStyle, toISODate, torontoToday } from '../components/schedule/styles';
import Skeleton from '../components/ui/Skeleton';
import PageHeader from '../components/ui/PageHeader';
import Button from '../components/ui/Button';
import Card from '../components/ui/Card';

const VIEW_MODES = [
  { key: 'weekly', label: 'Weekly' },
  { key: 'monthly', label: 'Monthly' },
  { key: 'yearly', label: 'Yearly' },
];

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'course', label: 'Courses' },
  { key: 'project', label: 'Projects' },
  { key: 'career', label: 'Career' },
];

function generateICSAndDownload(events) {
  let ics = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Acadvo//NONSGML v1.0//EN'
  ];

  events.forEach(e => {
    if (!e.date) return;
    const cleanDate = e.date.replace(/-/g, '');
    const desc = e.weight != null ? `Weight: ${e.weight}%` : '';
    ics.push('BEGIN:VEVENT');
    ics.push(`UID:${e.id || Math.random().toString(36).substr(2)}@acadvo.app`);
    ics.push(`DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').split('.')[0]}Z`);
    ics.push(`DTSTART;VALUE=DATE:${cleanDate}`);
    ics.push(`SUMMARY:${e.title}`);
    if (desc) ics.push(`DESCRIPTION:${desc}`);
    ics.push('END:VEVENT');
  });

  ics.push('END:VCALENDAR');

  const blob = new Blob([ics.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'acadvo-schedule.ics';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export default function SchedulePage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('weekly');
  const [filter, setFilter] = useState('all');
  const [weekOffset, setWeekOffset] = useState(0);
  const [monthOffset, setMonthOffset] = useState(0);

  useEffect(() => {
    getSchedule()
      .then(({ data }) => setEvents(data))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let list = events.filter(e => e.date);
    if (filter !== 'all') list = list.filter(e => e.category === filter);
    return list;
  }, [events, filter]);

  // Focus mode — next 24h
  const today = torontoToday();
  const tomorrowDate = new Date();
  tomorrowDate.setDate(tomorrowDate.getDate() + 1);
  const tomorrow = toISODate(tomorrowDate);
  const focusEvents = useMemo(() => {
    return filtered.filter(e => e.date >= today && e.date < tomorrow);
  }, [filtered, today, tomorrow]);

  const hasEvents = events.some(e => e.date);

  if (loading) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <Skeleton className="h-8 w-40" />
            <Skeleton className="h-4 w-64 mt-2" />
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="h-8 w-40 rounded-lg" />
            <Skeleton className="h-8 w-48 rounded-lg" />
          </div>
        </div>

        {/* Focus panel */}
        <div className="rounded-2xl border border-gray-200 dark:border-dark-700/50 bg-white/40 dark:bg-dark-800/40 p-5">
          <Skeleton className="h-3 w-40 mb-4" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-20 w-full rounded-xl" />
            ))}
          </div>
        </div>

        {/* View content */}
        <Skeleton className="h-72 w-full rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header row */}
      <PageHeader
        eyebrow="SCHEDULE"
        title="Schedule"
        subtitle="Academics & Career — all deadlines in one place"
        actions={
          events.length > 0 && (
            <Button variant="secondary" onClick={() => generateICSAndDownload(events)}>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              Export
            </Button>
          )
        }
      />

      {/* Toolbar: category filter + view mode */}
      <div className="flex items-center justify-end gap-3 flex-wrap">
        {/* Category filter */}
        <div className="relative flex bg-dark-800 rounded-lg p-0.5 border border-dark-700/50">
          {/* Sliding active indicator */}
          <div
            className="absolute top-0.5 bottom-0.5 bg-dark-950 dark:bg-dark-700 rounded-md transition-all duration-200 ease-out shadow-sm dark:shadow-none"
            style={{
              width: `${100 / FILTERS.length}%`,
              left: `${FILTERS.findIndex(f => f.key === filter) * (100 / FILTERS.length)}%`,
            }}
          />
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`relative z-10 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                filter === f.key ? 'text-dark-50' : 'text-dark-400 hover:text-dark-200'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* View mode segmented control */}
        <div className="relative flex bg-dark-800 rounded-lg p-0.5 border border-dark-700/50">
          {/* Sliding active indicator */}
          <div
            className="absolute top-0.5 bottom-0.5 bg-primary-600 rounded-md transition-all duration-200 ease-out"
            style={{
              width: `${100 / VIEW_MODES.length}%`,
              left: `${VIEW_MODES.findIndex(v => v.key === viewMode) * (100 / VIEW_MODES.length)}%`,
            }}
          />
          {VIEW_MODES.map(v => (
            <button
              key={v.key}
              onClick={() => { setViewMode(v.key); setWeekOffset(0); setMonthOffset(0); }}
              className={`relative z-10 px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                viewMode === v.key ? 'text-dark-50' : 'text-dark-400 hover:text-dark-200'
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {!hasEvents ? (
        /* Empty state */
        <Card className="p-16 text-center">
          <div className="relative z-10 flex flex-col items-center">
            <div className="icon-chip w-16 h-16 mb-6 rounded-2xl flex items-center justify-center text-primary-600 dark:text-primary-400">
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <h2 className="font-display text-3xl text-dark-50 mb-3">Your schedule is completely clear</h2>
            <p className="text-dark-400 text-sm max-w-md mx-auto">
              Upload a syllabus to auto-extract deadlines, or add a career target to start building your academic timeline.
            </p>
            <Link to="/degree" className="btn-accent mt-6 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all active:scale-[0.98]">
              Upload a syllabus
            </Link>
          </div>
        </Card>
      ) : (
        <>
          {/* Focus Mode — Next 24h (always visible) */}
          <Card className="p-5">
            <div className="relative">
              <div className="flex items-baseline gap-2 mb-4">
                <span className="eyebrow">Focus</span>
                <h2 className="font-display text-lg text-dark-50">Next 24 Hours</h2>
              </div>
              {focusEvents.length === 0 ? (
                <div className="py-6 flex flex-col items-center text-center">
                  <svg className="w-10 h-10 text-dark-500 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="font-display text-lg text-dark-50">Nothing due in the next 24 hours</p>
                  <p className="text-dark-400 text-xs mt-1">You're ahead of schedule.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {focusEvents.map(e => {
                    const s = getStyle(e.category);
                    return (
                      <div key={e.id} className={`rounded-xl border ${s.border} ${s.bg} p-3.5`}>
                        <p className="text-dark-50 text-sm font-medium truncate">{e.title}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full border ${s.badge} capitalize`}>{e.category}</span>
                          {e.weight != null && <span className={`text-xs font-semibold ${s.text} tabular-nums`}>{e.weight}%</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </Card>

          {/* Navigation arrows for weekly/monthly */}
          {(viewMode === 'weekly' || viewMode === 'monthly') && (
            <div className="flex items-center justify-between">
              <button
                onClick={() => viewMode === 'weekly' ? setWeekOffset(o => o - 1) : setMonthOffset(o => o - 1)}
                className="flex items-center gap-1 text-dark-400 hover:text-dark-50 text-sm transition"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Previous
              </button>
              <button
                onClick={() => { setWeekOffset(0); setMonthOffset(0); }}
                className="text-dark-400 hover:text-dark-50 text-xs transition px-3 py-1 rounded-lg hover:bg-dark-800"
              >
                Today
              </button>
              <button
                onClick={() => viewMode === 'weekly' ? setWeekOffset(o => o + 1) : setMonthOffset(o => o + 1)}
                className="flex items-center gap-1 text-dark-400 hover:text-dark-50 text-sm transition"
              >
                Next
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          )}

          {/* View content */}
          {viewMode === 'weekly' && <WeeklyView events={filtered} weekOffset={weekOffset} />}
          {viewMode === 'monthly' && <MonthlyView events={filtered} monthOffset={monthOffset} />}
          {viewMode === 'yearly' && <YearlyView events={filtered} />}
        </>
      )}
    </div>
  );
}
