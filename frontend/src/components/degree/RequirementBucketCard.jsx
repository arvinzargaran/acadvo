import Card from '../ui/Card';
import ProgressBar from '../ui/ProgressBar';
import Badge from '../ui/Badge';

const statusColors = {
  completed: 'green',
  in_progress: 'yellow',
  planned: 'blue',
  not_scheduled: 'gray',
};

export default function RequirementBucketCard({ requirement, courses }) {
  const bucketCourses = courses.filter(c => c.requirement_bucket_id === requirement.id);
  const completed = bucketCourses
    .filter(c => c.status === 'completed')
    .reduce((sum, c) => sum + parseFloat(c.credit_value), 0);
  const required = parseFloat(requirement.credits_required);
  const pct = required > 0 ? Math.round((completed / required) * 100) : 0;
  const atRisk = (required - completed) > required * 0.5 && (required - completed) > 0;

  return (
    <Card className={atRisk ? 'border-red-500/50' : ''}>
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="font-display text-lg text-dark-50">{requirement.bucket_name}</h3>
        {atRisk && <Badge color="red" dot>At Risk</Badge>}
      </div>
      <ProgressBar
        value={pct}
        label={`${completed} / ${required} credits`}
      />
      {bucketCourses.length > 0 && (
        <div className="mt-3 space-y-1">
          {bucketCourses.map(c => (
            <div key={c.id} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className="font-medium text-dark-50">{c.course_code}</span>
                <span className="text-dark-400">{c.course_name}</span>
              </div>
              <div className="flex items-center gap-2">
                {c.grade && <span className="text-dark-300 text-xs">{c.grade}</span>}
                {c.term && <span className="text-dark-400 text-xs">{c.term}</span>}
                <Badge color={statusColors[c.status]} variant="label" dot>{c.status.replace('_', ' ')}</Badge>
              </div>
            </div>
          ))}
        </div>
      )}
      {requirement.notes && (
        <p className="text-dark-400 text-xs mt-2">{requirement.notes}</p>
      )}
    </Card>
  );
}
