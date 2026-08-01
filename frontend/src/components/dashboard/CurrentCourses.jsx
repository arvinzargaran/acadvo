import Card from '../ui/Card';
import Badge from '../ui/Badge';

const statusColors = {
  completed: 'green',
  in_progress: 'yellow',
  planned: 'blue',
  not_scheduled: 'gray',
};

export default function CurrentCourses({ courses, bento = false }) {
  const current = courses?.filter(c => c.status === 'in_progress') || [];

  const content = (
    <>
      <h3 className="text-white font-semibold mb-3">Current Courses</h3>
      {current.length === 0 ? (
        <div className="py-2">
          <p className="font-display text-lg text-white">Nothing in progress</p>
          <p className="text-dark-400 text-sm mt-0.5">Courses you mark as in-progress will show up here.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {current.map(c => (
            <div key={c.id} className={`flex items-center justify-between rounded-lg px-3 py-2 ${bento ? 'bg-white/5 border border-white/5' : 'bg-dark-700/50'}`}>
              <div>
                <span className="text-white text-sm font-medium">{c.course_code}</span>
                <span className="text-dark-400 text-sm ml-2">{c.course_name}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-dark-400 text-xs">{c.term}</span>
                <Badge color={statusColors[c.status]}>{c.status.replace('_', ' ')}</Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );

  if (bento) return <div>{content}</div>;
  return <Card>{content}</Card>;
}
