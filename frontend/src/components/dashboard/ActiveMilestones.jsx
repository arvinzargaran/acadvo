import Card from '../ui/Card';
import Badge from '../ui/Badge';

const statusColors = {
  pending: 'gray',
  in_progress: 'yellow',
  complete: 'green',
  overdue: 'red',
};

export default function ActiveMilestones({ projects }) {
  const activeMilestones = [];
  projects?.forEach(p => {
    p.milestones
      ?.filter(m => m.status === 'in_progress' || m.status === 'pending')
      .slice(0, 2)
      .forEach(m => {
        activeMilestones.push({ ...m, projectName: p.name });
      });
  });

  return (
    <Card>
      <h3 className="text-white font-semibold mb-3">Active Milestones</h3>
      {activeMilestones.length === 0 ? (
        <p className="text-dark-400 text-sm">No active milestones</p>
      ) : (
        <div className="space-y-2">
          {activeMilestones.slice(0, 5).map(m => (
            <div key={m.id} className="bg-dark-700/50 rounded-lg px-3 py-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white text-sm">{m.title}</p>
                  <p className="text-dark-400 text-xs">{m.projectName}</p>
                </div>
                <div className="flex items-center gap-2">
                  {m.target_date && (
                    <span className="text-dark-400 text-xs">{m.target_date}</span>
                  )}
                  <Badge color={statusColors[m.status]}>{m.status}</Badge>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
