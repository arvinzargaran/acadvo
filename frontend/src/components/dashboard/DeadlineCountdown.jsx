import Card from '../ui/Card';

export default function DeadlineCountdown({ events }) {
  const hardDeadlines = events
    .filter(e => e.is_hard_deadline)
    .sort((a, b) => new Date(a.event_date) - new Date(b.event_date));

  const next = hardDeadlines[0];
  if (!next) {
    return (
      <Card className="text-center">
        <p className="text-dark-400 text-sm">No upcoming hard deadlines</p>
      </Card>
    );
  }

  const days = Math.ceil((new Date(next.event_date) - new Date()) / (1000 * 60 * 60 * 24));
  const urgencyColor = days <= 7 ? 'text-red-400' : days <= 30 ? 'text-yellow-400' : 'text-primary-400';

  return (
    <Card>
      <p className="text-dark-400 text-sm mb-1">Next Hard Deadline</p>
      <p className={`text-4xl font-bold ${urgencyColor}`}>{days}</p>
      <p className="text-dark-300 text-sm">days remaining</p>
      <p className="text-dark-50 mt-2 font-medium">{next.title}</p>
      <p className="text-dark-400 text-xs">{next.event_date}</p>
    </Card>
  );
}
