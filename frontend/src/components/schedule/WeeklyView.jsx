import { useMemo } from 'react';
import EventCard from './EventCard';
import { toISODate, torontoToday, getStyle, daysUntil, daysRemainingBadge } from './styles';

function getWeekStart(d) {
  const date = new Date(d);
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day; // Monday start
  date.setDate(date.getDate() + diff);
  return date;
}

export default function WeeklyView({ events, weekOffset = 0 }) {
  const today = torontoToday();

  const weekDays = useMemo(() => {
    const start = getWeekStart(new Date());
    start.setDate(start.getDate() + weekOffset * 7);
    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(start);
      d.setDate(d.getDate() + i);
      const key = toISODate(d);
      days.push({
        key,
        dayName: d.toLocaleDateString('en-US', { weekday: 'short' }),
        dayNum: d.getDate(),
        month: d.toLocaleDateString('en-US', { month: 'short' }),
        isToday: key === today,
        events: events.filter(e => e.date === key),
      });
    }
    return days;
  }, [events, weekOffset, today]);

  return (
    <div className="space-y-4">
      {/* Horizontal day headers */}
      <div className="grid grid-cols-7 gap-2">
        {weekDays.map(day => (
          <div
            key={day.key}
            className={`text-center rounded-xl border p-3 transition-all duration-150 ${
              day.isToday
                ? 'border-emerald-500/50 bg-emerald-500/10 ring-1 ring-emerald-500/30'
                : day.events.length > 0
                  ? 'border-dark-700/50 bg-dark-800/60 hover:bg-white/[0.06]'
                  : 'border-dark-700/30 bg-dark-800/30 hover:bg-white/[0.06]'
            }`}
          >
            <p className={`text-xs font-medium ${day.isToday ? 'text-emerald-400' : 'text-dark-400'}`}>
              {day.dayName}
            </p>
            <p className={`font-display tabular-nums text-lg mt-0.5 ${day.isToday ? 'text-dark-50' : day.events.length > 0 ? 'text-dark-200' : 'text-dark-500'}`}>
              {day.dayNum}
            </p>
            {day.events.length > 0 && (
              <div className="flex justify-center gap-1 mt-1.5">
                {day.events.slice(0, 4).map(e => (
                  <div key={e.id} className={`w-1.5 h-1.5 rounded-full ${getStyle(e.category).dotSolid}`} />
                ))}
                {day.events.length > 4 && <span className="text-dark-500 text-[8px]">+{day.events.length - 4}</span>}
              </div>
            )}
            {day.isToday && (
              <div className="w-1 h-1 rounded-full bg-primary-500 mx-auto mt-1" />
            )}
          </div>
        ))}
      </div>

      {/* Event details per day */}
      <div className="space-y-4">
        {weekDays.map(day => {
          if (day.events.length === 0) return null;
          return (
            <div key={day.key}>
              <div className="flex items-baseline gap-2 mb-2">
                <span className={`font-display text-base ${day.isToday ? 'text-dark-50' : 'text-dark-300'}`}>
                  {day.isToday ? 'Today' : day.dayName}
                </span>
                <span className="text-xs text-dark-500">{day.month} {day.dayNum}</span>
                <span className="text-[10px] text-dark-500 bg-dark-800 px-1.5 py-0.5 rounded-full">{day.events.length}</span>
              </div>
              <div className="space-y-2">
                {day.events.map(e => (
                  <EventCard key={e.id} event={e} />
                ))}
              </div>
            </div>
          );
        })}

        {weekDays.every(d => d.events.length === 0) && (
          <div className="text-center py-8">
            <p className="font-display text-xl text-dark-50">A clear week</p>
            <p className="text-dark-400 text-sm mt-1">Nothing scheduled — use the arrows to look ahead.</p>
          </div>
        )}
      </div>
    </div>
  );
}
