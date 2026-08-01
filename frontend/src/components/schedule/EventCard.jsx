import { getStyle, daysUntil, daysRemainingBadge } from './styles';

export default function EventCard({ event, compact = false }) {
  const s = getStyle(event.category);
  const days = event.date ? daysUntil(event.date) : null;
  const badge = days !== null ? daysRemainingBadge(days) : null;

  if (compact) {
    return (
      <div className={`flex items-center gap-2 rounded-lg border ${s.border} bg-dark-800 px-2.5 py-1.5 transition hover:bg-dark-800/80`}>
        <div className={`w-1.5 h-1.5 rounded-full ${s.dotSolid} flex-shrink-0`} />
        <span className="text-dark-50 text-xs font-medium truncate flex-1">{event.title}</span>
        {badge && (
          <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${badge.cls} flex-shrink-0`}>{badge.label}</span>
        )}
      </div>
    );
  }

  return (
    <div className={`rounded-xl border ${s.border} bg-dark-800 p-3 transition hover:bg-dark-800/80`}>
      <div className="flex items-center gap-3">
        <div className={`w-1 h-8 rounded-full ${s.dot} flex-shrink-0`} />
        <div className="flex-1 min-w-0">
          <p className="text-dark-50 text-sm font-medium truncate">{event.title}</p>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            <span className={`text-[10px] px-2 py-0.5 rounded-full border ${s.badge} capitalize`}>{event.category}</span>
            <span className="text-dark-500 text-[10px]">{event.type}</span>
            {event.notes && <span className="text-dark-500 text-[10px] truncate max-w-[120px]">{event.notes}</span>}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          {event.weight != null && (
            <span className={`text-xs font-semibold ${s.text}`}>{event.weight}%</span>
          )}
          {badge && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full border whitespace-nowrap ${badge.cls}`}>{badge.label}</span>
          )}
        </div>
      </div>
    </div>
  );
}
