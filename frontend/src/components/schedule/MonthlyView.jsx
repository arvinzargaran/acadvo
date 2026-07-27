import { useMemo, useState } from 'react';
import { toISODate, torontoToday, getStyle } from './styles';
import DayAgendaDrawer from './DayAgendaDrawer';

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function MonthlyView({ events, monthOffset = 0 }) {
  const today = torontoToday();
  const [selectedDay, setSelectedDay] = useState(null);

  const { weeks, monthLabel } = useMemo(() => {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + monthOffset;
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const monthLabel = firstDay.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

    // Monday = 0, Sunday = 6
    let startDow = firstDay.getDay() - 1;
    if (startDow < 0) startDow = 6;

    const eventsByDate = {};
    for (const e of events) {
      if (!e.date) continue;
      if (!eventsByDate[e.date]) eventsByDate[e.date] = [];
      eventsByDate[e.date].push(e);
    }

    const weeks = [];
    let week = [];
    // Fill leading blanks
    for (let i = 0; i < startDow; i++) week.push(null);

    for (let day = 1; day <= lastDay.getDate(); day++) {
      const d = new Date(year, month, day);
      const key = toISODate(d);
      week.push({ key, day, events: eventsByDate[key] || [], isToday: key === today });
      if (week.length === 7) {
        weeks.push(week);
        week = [];
      }
    }
    // Fill trailing blanks
    if (week.length > 0) {
      while (week.length < 7) week.push(null);
      weeks.push(week);
    }

    return { weeks, monthLabel };
  }, [events, monthOffset, today]);

  const selectedEvents = useMemo(() => {
    if (!selectedDay) return [];
    return events.filter(e => e.date === selectedDay);
  }, [events, selectedDay]);

  return (
    <>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white">{monthLabel}</h2>

        {/* Calendar grid */}
        <div className="bg-dark-800 border border-dark-700/50 rounded-2xl overflow-hidden">
          {/* Day name headers */}
          <div className="grid grid-cols-7 border-b border-dark-700/50">
            {DAY_NAMES.map(name => (
              <div key={name} className="text-center py-2">
                <span className="text-dark-400 text-xs font-medium">{name}</span>
              </div>
            ))}
          </div>

          {/* Week rows */}
          {weeks.map((week, wi) => (
            <div key={wi} className="grid grid-cols-7 border-b border-dark-700/30 last:border-0">
              {week.map((cell, ci) => {
                if (!cell) return <div key={ci} className="min-h-[80px] bg-dark-900/30" />;
                const isSelected = selectedDay === cell.key;
                return (
                  <button
                    key={cell.key}
                    onClick={() => setSelectedDay(isSelected ? null : cell.key)}
                    className={`group/cell min-h-[80px] p-2 text-left transition-all duration-150 border-r border-dark-700/20 last:border-r-0 relative ${
                      cell.isToday
                        ? 'bg-emerald-500/8 ring-1 ring-inset ring-emerald-500/30'
                        : isSelected
                          ? 'bg-dark-700/40'
                          : 'hover:bg-white/[0.06]'
                    }`}
                  >
                    {/* Day number */}
                    <span className={`text-xs font-semibold block mb-1.5 ${
                      cell.isToday
                        ? 'text-emerald-400'
                        : cell.events.length > 0
                          ? 'text-white'
                          : 'text-dark-500 group-hover/cell:text-dark-300'
                    }`}>
                      {cell.isToday ? (
                        <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-500 text-white text-[10px] font-bold">
                          {cell.day}
                        </span>
                      ) : cell.day}
                    </span>

                    {/* Color-coded dots */}
                    {cell.events.length > 0 && (
                      <div className="flex flex-wrap gap-0.5">
                        {cell.events.slice(0, 6).map(e => (
                          <div
                            key={e.id}
                            className={`w-2 h-2 rounded-sm ${getStyle(e.category).dotSolid}`}
                            title={e.title}
                          />
                        ))}
                        {cell.events.length > 6 && (
                          <span className="text-dark-500 text-[8px] leading-none">+{cell.events.length - 6}</span>
                        )}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-sm bg-primary-500" /><span className="text-dark-400 text-xs">Course</span></div>
          <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-sm bg-emerald-500" /><span className="text-dark-400 text-xs">Project</span></div>
          <div className="flex items-center gap-1.5"><div className="w-2 h-2 rounded-sm bg-amber-500" /><span className="text-dark-400 text-xs">Career</span></div>
          <div className="ml-auto text-dark-500 text-[10px]">Click a day for details</div>
        </div>
      </div>

      {/* Side drawer */}
      <DayAgendaDrawer
        dateKey={selectedDay}
        events={selectedEvents}
        onClose={() => setSelectedDay(null)}
      />
    </>
  );
}
