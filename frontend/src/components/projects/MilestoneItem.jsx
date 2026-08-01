import Badge from '../ui/Badge';

const statusColors = {
  pending: 'gray',
  in_progress: 'yellow',
  complete: 'green',
  overdue: 'red',
};

export default function MilestoneItem({ milestone, onUpdate }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={milestone.status === 'complete'}
          onChange={() => onUpdate(milestone.id, {
            status: milestone.status === 'complete' ? 'pending' : 'complete',
          })}
          className="rounded border-dark-600 bg-dark-800 text-primary-600 focus:ring-primary-500"
        />
        <span className={`text-sm ${milestone.status === 'complete' ? 'text-dark-400 line-through' : 'text-dark-50'}`}>
          {milestone.title}
        </span>
      </div>
      <div className="flex items-center gap-2">
        {milestone.target_date && (
          <span className="text-dark-400 text-xs">{milestone.target_date}</span>
        )}
        <Badge color={statusColors[milestone.status]} variant="label" dot>{milestone.status}</Badge>
      </div>
    </div>
  );
}
