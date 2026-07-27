import Badge from '../ui/Badge';

const statusColors = {
  pending: 'gray',
  in_progress: 'yellow',
  complete: 'green',
  overdue: 'red',
};

const icons = {
  complete: '✅',
  in_progress: '🔄',
  pending: '⬜',
  overdue: '🚨',
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
    <div className="space-y-1.5">
      <p className="text-dark-400 text-xs font-medium">Milestones</p>
      {sorted.map(m => (
        <div
          key={m.id}
          className="flex items-center justify-between bg-dark-700/50 rounded-lg px-3 py-2 cursor-pointer hover:bg-dark-700 transition"
          onClick={() => cycleStatus(m)}
        >
          <div className="flex items-center gap-2">
            <span>{icons[m.status] || '⬜'}</span>
            <span className={`text-sm ${m.status === 'complete' ? 'text-dark-400 line-through' : 'text-white'}`}>
              {m.title}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {m.target_date && (
              <span className="text-dark-400 text-xs">{m.target_date}</span>
            )}
            <Badge color={statusColors[m.status]}>{m.status}</Badge>
          </div>
        </div>
      ))}
    </div>
  );
}
