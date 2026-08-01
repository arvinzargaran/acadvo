import { useState } from 'react';
import Card from '../ui/Card';

const defaultCategories = [
  { name: 'Easy Problems', target: 30, color: 'bg-green-500' },
  { name: 'Medium Problems', target: 30, color: 'bg-yellow-500' },
  { name: 'Hard Problems', target: 10, color: 'bg-red-500' },
  { name: 'Mock Interviews', target: 5, color: 'bg-primary-500' },
];

export default function DSATracker() {
  // Simple local state tracker — could be persisted later
  const [counts, setCounts] = useState(() => {
    const saved = localStorage.getItem('acadvo_dsa');
    return saved ? JSON.parse(saved) : defaultCategories.map(() => 0);
  });

  const update = (index, delta) => {
    setCounts(prev => {
      const next = [...prev];
      next[index] = Math.max(0, next[index] + delta);
      localStorage.setItem('acadvo_dsa', JSON.stringify(next));
      return next;
    });
  };

  return (
    <Card>
      <div className="flex items-center gap-3 mb-4">
        <span className="icon-chip w-8 h-8 rounded-lg flex items-center justify-center text-primary-500">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
        </span>
        <h3 className="font-display text-xl tracking-tight text-dark-50">DSA Prep Tracker</h3>
      </div>
      <div className="space-y-3">
        {defaultCategories.map((cat, i) => {
          const pct = Math.min(100, Math.round((counts[i] / cat.target) * 100));
          return (
            <div key={cat.name}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-dark-300">{cat.name}</span>
                <div className="flex items-center gap-2">
                  <span className="font-display tabular-nums text-dark-400">{counts[i]} / {cat.target}</span>
                  <button
                    onClick={() => update(i, -1)}
                    className="w-6 h-6 rounded bg-dark-700 text-dark-300 hover:text-dark-50 text-xs"
                  >
                    -
                  </button>
                  <button
                    onClick={() => update(i, 1)}
                    className="w-6 h-6 rounded bg-dark-700 text-dark-300 hover:text-dark-50 text-xs"
                  >
                    +
                  </button>
                </div>
              </div>
              <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${cat.color}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
