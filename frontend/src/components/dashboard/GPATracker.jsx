import Card from '../ui/Card';

export default function GPATracker({ summary }) {
  if (!summary || summary.cumulative_gpa === null || summary.cumulative_gpa === undefined) {
    return (
      <Card>
        <h3 className="text-white font-semibold mb-2">GPA</h3>
        <p className="text-dark-400 text-sm">No graded courses yet.</p>
      </Card>
    );
  }

  const gpa = summary.cumulative_gpa;
  const color = gpa >= 3.5 ? 'text-green-400' : gpa >= 3.0 ? 'text-primary-400' : gpa >= 2.5 ? 'text-yellow-400' : 'text-red-400';
  const semesters = summary.semester_gpas || [];

  return (
    <Card>
      <h3 className="text-white font-semibold mb-3">GPA</h3>
      <div className="flex items-end gap-4 mb-4">
        <div>
          <p className="text-dark-400 text-xs">Cumulative</p>
          <p className={`text-3xl font-bold ${color}`}>{gpa.toFixed(2)}</p>
        </div>
        {semesters.length > 1 && (
          <div className="flex-1 flex items-end gap-1 h-16">
            {semesters.map((s, i) => {
              const height = Math.max((s.gpa / 4.0) * 100, 10);
              const barColor = s.gpa >= 3.5 ? 'bg-green-500' : s.gpa >= 3.0 ? 'bg-primary-500' : s.gpa >= 2.5 ? 'bg-yellow-500' : 'bg-red-500';
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1" title={`${s.term}: ${s.gpa.toFixed(2)}`}>
                  <div className={`w-full rounded-sm ${barColor}`} style={{ height: `${height}%` }} />
                  <span className="text-dark-500 text-[9px] truncate w-full text-center">{s.term.replace(/\s+/g, '\n').split('\n').pop()}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
      {semesters.length > 0 && (
        <div className="text-xs text-dark-500">
          Latest: {semesters[semesters.length - 1]?.term} — {semesters[semesters.length - 1]?.gpa.toFixed(2)}
        </div>
      )}
    </Card>
  );
}
