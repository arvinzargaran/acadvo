import Card from '../ui/Card';

function daysUntil(dateStr) {
  return Math.ceil((new Date(dateStr) - new Date()) / (1000 * 60 * 60 * 24));
}

function urgencyColor(days) {
  if (days < 0) return 'text-red-400 bg-red-500/10 border-red-500/30';
  if (days <= 3) return 'text-red-400 bg-red-500/10 border-red-500/30';
  if (days <= 7) return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30';
  if (days <= 30) return 'text-primary-400 bg-primary-500/10 border-primary-500/30';
  return 'text-dark-300 bg-dark-700 border-dark-600';
}

function urgencyBadge(days) {
  if (days < 0) return 'Overdue';
  if (days === 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  return `${days}d`;
}

export default function UpcomingDeadlines({ events, projects }) {
  const items = [];

  // Career timeline events with dates
  events?.forEach(e => {
    if (e.event_date) {
      items.push({
        id: `event-${e.id}`,
        title: e.title,
        date: e.event_date,
        source: e.is_hard_deadline ? 'Deadline' : 'Event',
        icon: e.is_hard_deadline ? '!' : null,
      });
    }
  });

  // Project milestones with target dates
  projects?.forEach(p => {
    p.milestones?.forEach(m => {
      if (m.target_date && m.status !== 'complete') {
        items.push({
          id: `milestone-${m.id}`,
          title: m.title,
          date: m.target_date,
          source: p.name,
          icon: null,
        });
      }
    });
  });

  // Sort by date, only show upcoming (and recently overdue)
  const sorted = items
    .map(item => ({ ...item, days: daysUntil(item.date) }))
    .filter(item => item.days >= -7)
    .sort((a, b) => a.days - b.days)
    .slice(0, 8);

  return (
    <Card>
      <h3 className="text-white font-semibold mb-3">Upcoming Deadlines</h3>
      {sorted.length === 0 ? (
        <p className="text-dark-400 text-sm">No upcoming deadlines — you're all clear!</p>
      ) : (
        <div className="space-y-2">
          {sorted.map(item => (
            <div key={item.id} className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${urgencyColor(item.days)}`}>
              <div className="flex-shrink-0 w-10 text-center">
                <span className="text-xs font-bold">{urgencyBadge(item.days)}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate text-white">{item.title}</p>
                <p className="text-xs opacity-60">{item.source}</p>
              </div>
              <span className="text-xs opacity-50 flex-shrink-0">{item.date}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
