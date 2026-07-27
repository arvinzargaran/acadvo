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
        <div className="w-10 h-10 bg-dark-700 rounded-lg flex items-center justify-center text-lg font-bold text-primary-400">
          {target.company_name[0]}
        </div>
        <div>
          <h3 className="text-white font-medium">{target.company_name}</h3>
          <div className="flex items-center gap-2 text-sm text-dark-400">
            {target.role_type && <span>{target.role_type}</span>}
            {target.location && <span>• {target.location}</span>}
            {target.target_term && <span>• {target.target_term}</span>}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Badge color={statusColors[target.status]}>{target.status}</Badge>
        <button onClick={() => onEdit(target)} className="text-primary-400 hover:text-primary-300 text-sm">Edit</button>
        <button onClick={() => onDelete(target.id)} className="text-red-400 hover:text-red-300 text-sm">Delete</button>
      </div>
    </Card>
  );
}
