import { useState, useEffect } from 'react';
import Card from '../ui/Card';
import Skeleton from '../ui/Skeleton';
import { getWeeklySummary } from '../../api/dashboard';

const CACHE_KEY = 'acadvo_weekly_summary';
const CACHE_TTL = 12 * 60 * 60 * 1000; // 12 hours

export default function WeeklyCheckin({ bento = false }) {
  const [summary, setSummary] = useState(() => {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached) {
      try {
        const { data, timestamp } = JSON.parse(cached);
        if (Date.now() - timestamp < CACHE_TTL) return data;
      } catch {}
    }
    return null;
  });
  
  const [loading, setLoading] = useState(!summary);
  const [error, setError] = useState(null);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getWeeklySummary();
      setSummary(res.data);
      localStorage.setItem(CACHE_KEY, JSON.stringify({ data: res.data, timestamp: Date.now() }));
    } catch {
      setError('Failed to generate summary.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!summary) generate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const W = bento ? 'div' : Card;

  if (loading) {
    return (
      <W>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary-500 animate-pulse" />
            <h3 className="text-white font-semibold">Weekly Check-in</h3>
          </div>
          <span className="text-dark-400 text-xs">Generating…</span>
        </div>
        <Skeleton className="h-3 w-3/4 mb-3" />
        <Skeleton className="h-2.5 w-20 mb-2" />
        <Skeleton className="h-3 w-full mb-1.5" />
        <Skeleton className="h-3 w-5/6 mb-3" />
        <Skeleton className="h-2.5 w-24 mb-2" />
        <Skeleton className="h-3 w-full mb-1.5" />
        <Skeleton className="h-3 w-2/3" />
      </W>
    );
  }

  if (!summary) {
    return (
      <W>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-white font-semibold">Weekly Check-in</h3>
            <p className="text-dark-400 text-xs mt-0.5">AI-powered progress summary</p>
          </div>
          <button
            onClick={generate}
            className="px-3 py-1.5 bg-primary-600 hover:bg-primary-700 text-white text-sm rounded-lg transition-all"
          >
            Generate
          </button>
        </div>
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
      </W>
    );
  }

  return (
    <W>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-semibold">Weekly Check-in</h3>
        <button onClick={generate} className="text-dark-400 hover:text-white text-xs transition-colors">
          Refresh
        </button>
      </div>

      <p className="text-dark-300 text-sm mb-3">{summary.greeting}</p>

      {summary.highlights?.length > 0 && (
        <div className="mb-3">
          <p className="text-green-400 text-xs font-medium mb-1">Highlights</p>
          {summary.highlights.map((h, i) => (
            <p key={i} className="text-dark-300 text-sm flex gap-2">
              <span className="text-green-500">+</span> {h}
            </p>
          ))}
        </div>
      )}

      {summary.action_items?.length > 0 && (
        <div className="mb-3">
          <p className="text-primary-400 text-xs font-medium mb-1">Action Items</p>
          {summary.action_items.map((a, i) => (
            <p key={i} className="text-dark-300 text-sm flex gap-2">
              <span className="text-primary-500">-</span> {a}
            </p>
          ))}
        </div>
      )}

      {summary.motivation && (
        <p className="text-dark-500 text-xs italic mt-2 border-t border-dark-700 pt-2">
          {summary.motivation}
        </p>
      )}
    </W>
  );
}
