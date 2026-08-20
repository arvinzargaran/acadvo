import Card from '../ui/Card';
import Badge from '../ui/Badge';

const severityColors = { high: 'red', medium: 'yellow', low: 'blue' };

export default function NextActions({ suggestions, onAccept, onDismiss }) {
  if (!suggestions || suggestions.length === 0) {
    return (
      <Card>
        <h3 className="text-dark-50 font-semibold mb-2">Next Actions</h3>
        <p className="text-dark-400 text-sm">No pending suggestions. Ask your advisor for recommendations.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="text-dark-50 font-semibold mb-3">Next Actions</h3>
      <div className="space-y-3">
        {suggestions.slice(0, 3).map(s => (
          <div key={s.id} className="bg-dark-700/50 rounded-lg p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <Badge color={severityColors[s.severity] || 'gray'}>{s.suggestion_type}</Badge>
                  {s.severity && <Badge color={severityColors[s.severity]}>{s.severity}</Badge>}
                </div>
                <p className="text-dark-200 text-sm">{s.content}</p>
              </div>
              <div className="flex gap-1 shrink-0">
                <button
                  onClick={() => onAccept(s.id)}
                  className="text-green-400 hover:text-green-300 text-xs px-2 py-1 rounded bg-dark-600"
                >
                  Accept
                </button>
                <button
                  onClick={() => onDismiss(s.id)}
                  className="text-dark-400 hover:text-dark-300 text-xs px-2 py-1 rounded bg-dark-600"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
