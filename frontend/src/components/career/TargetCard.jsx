import Card from '../ui/Card';
import Badge from '../ui/Badge';

const statusColors = {
  researching: 'blue',
  applied: 'yellow',
  interviewing: 'yellow',
  offer: 'green',
  rejected: 'red',
};

export default function TargetCard({ target, onEdit, onDelete }) {
  return (
    <Card className="flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="icon-chip w-11 h-11 rounded-xl flex items-center justify-center font-display text-xl text-primary-500">
          {target.company_name[0]}
        </div>
        <div>
          <h3 className="font-display text-lg tracking-tight text-dark-50">{target.company_name}</h3>
          <div className="flex items-center gap-2 text-sm text-dark-400">
            {target.role_type && <span>{target.role_type}</span>}
            {target.location && <span>• {target.location}</span>}
            {target.target_term && <span>• {target.target_term}</span>}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Badge color={statusColors[target.status]} dot>{target.status}</Badge>
        <button onClick={() => onEdit(target)} className="text-primary-500 hover:text-primary-400 text-sm">Edit</button>
        <button onClick={() => onDelete(target.id)} className="text-red-400 hover:text-red-300 text-sm">Delete</button>
      </div>
    </Card>
  );
}
