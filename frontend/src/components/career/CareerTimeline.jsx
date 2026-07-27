import Badge from '../ui/Badge';

const categoryColors = {
  deadline: 'red',
  milestone: 'yellow',
  goal: 'green',
  co_op: 'blue',
  academic: 'gray',
};

export default function CareerTimeline({ events }) {
  if (!events || events.length === 0) {
    return <p className="text-dark-400 text-sm">No timeline events yet.</p>;
  }

  const sorted = [...events].sort((a, b) => new Date(a.event_date) - new Date(b.event_date));

  return (
    <div className="relative">
      <div className="absolute left-4 top-0 bottom-0 w-px bg-dark-700" />
      <div className="space-y-4">
        {sorted.map(evt => {
          const days = Math.ceil((new Date(evt.event_date) - new Date()) / (1000 * 60 * 60 * 24));
          const isPast = days < 0;

          return (
            <div key={evt.id} className="relative flex items-start gap-4 pl-10">
              <div className={`absolute left-3 top-1.5 w-3 h-3 rounded-full border-2 ${isPast ? 'bg-dark-500 border-dark-500' : 'bg-primary-500 border-primary-500'}`} />
              <div className={`flex-1 ${isPast ? 'opacity-50' : ''}`}>
                <div className="flex items-center gap-2">
                  <span className="text-white text-sm font-medium">{evt.title}</span>
                  <Badge color={categoryColors[evt.category]}>{evt.category.replace('_', ' ')}</Badge>
                  {evt.is_hard_deadline && <Badge color="red">Hard</Badge>}
                </div>
                <div className="flex items-center gap-2 text-xs text-dark-400 mt-0.5">
                  <span>{evt.event_date}</span>
                  <span>• {isPast ? `${Math.abs(days)}d ago` : `in ${days}d`}</span>
                </div>
                {evt.description && <p className="text-dark-300 text-sm mt-1">{evt.description}</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
