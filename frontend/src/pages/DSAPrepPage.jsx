import { useState, useEffect } from 'react';
import Card from '../components/ui/Card';
import ProgressRing from '../components/ui/ProgressRing';
import ProgressBar from '../components/ui/ProgressBar';
import Button from '../components/ui/Button';
import Skeleton from '../components/ui/Skeleton';
import PageHeader from '../components/ui/PageHeader';
import Badge from '../components/ui/Badge';
import { listProblems, createProblem, updateProblem, deleteProblem, getStats, getSettings, updateSettings } from '../api/dsa';
import { safeExternalUrl } from '../utils/urls';

const WEEKLY_GOAL_KEY = 'dsa_weekly_goal';

function clampGoal(value) {
  const n = parseInt(value, 10);
  if (Number.isNaN(n)) return 1;
  return Math.max(1, Math.min(100, n));
}

const PATTERNS = [
  'Arrays & Hashing',
  'Two Pointers',
  'Sliding Window',
  'Stack',
  'Binary Search',
  'Linked Lists',
  'Trees',
  'Graphs',
  'Dynamic Programming',
  'Greedy',
  'Backtracking',
  'Bit Manipulation',
];

const DIFFICULTY_COLORS = {
  easy: '#4ade80',
  medium: '#facc15',
  hard: '#f87171',
};

const STATUS_LABELS = {
  not_started: 'Not Started',
  attempted: 'Attempted',
  solved: 'Solved',
};

export default function DSAPrepPage() {
  const [problems, setProblems] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [patternFilter, setPatternFilter] = useState('all');
  const [weeklyGoal, setWeeklyGoal] = useState(7);
  const [showAdd, setShowAdd] = useState(false);
  const [newProblem, setNewProblem] = useState({
    title: '',
    difficulty: 'easy',
    pattern: PATTERNS[0],
    leetcode_url: '',
    notes: '',
  });
  const [saving, setSaving] = useState(false);

  async function refreshData() {
    try {
      const [probRes, statsRes] = await Promise.all([listProblems(), getStats()]);
      setProblems(probRes.data);
      setStats(statsRes.data);
    } catch {
      // API errors handled by interceptor
    }
  }

  async function loadSettings() {
    try {
      const res = await getSettings();
      const local = localStorage.getItem(WEEKLY_GOAL_KEY);
      // One-time migration: if the server has no stored goal yet but a value
      // lingers in localStorage, push it up once, then clear the local copy.
      if (res.data.is_default && local != null) {
        const val = clampGoal(local);
        const put = await updateSettings({ weekly_goal: val });
        setWeeklyGoal(put.data.weekly_goal);
        localStorage.removeItem(WEEKLY_GOAL_KEY);
      } else {
        setWeeklyGoal(res.data.weekly_goal);
        // Server is now the source of truth; drop any stale local copy.
        if (local != null) localStorage.removeItem(WEEKLY_GOAL_KEY);
      }
    } catch {
      // API errors handled by interceptor; keep the default goal.
    }
  }

  useEffect(() => {
    async function load() {
      await Promise.all([refreshData(), loadSettings()]);
      setLoading(false);
    }
    load();
  }, []);

  async function handleGoalChange(value) {
    const clamped = clampGoal(value);
    const previous = weeklyGoal;
    setWeeklyGoal(clamped); // optimistic
    try {
      await updateSettings({ weekly_goal: clamped });
    } catch {
      setWeeklyGoal(previous); // revert on failure
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!newProblem.title.trim()) return;
    setSaving(true);
    try {
      await createProblem({
        title: newProblem.title.trim(),
        difficulty: newProblem.difficulty,
        pattern: newProblem.pattern,
        leetcode_url: newProblem.leetcode_url.trim() || null,
        notes: newProblem.notes.trim() || null,
      });
      setNewProblem({ title: '', difficulty: 'easy', pattern: PATTERNS[0], leetcode_url: '', notes: '' });
      setShowAdd(false);
      await refreshData();
    } finally {
      setSaving(false);
    }
  }

  async function handleMarkSolved(problem) {
    await updateProblem(problem.id, { status: 'solved' });
    await refreshData();
  }

  async function handleStatusChange(problem, status) {
    await updateProblem(problem.id, { status });
    await refreshData();
  }

  async function handleDelete(id) {
    await deleteProblem(id);
    await refreshData();
  }

  const filteredProblems = patternFilter === 'all'
    ? problems
    : problems.filter(p => p.pattern === patternFilter);

  // Difficulty counts (all problems, not just solved)
  const easySolved = stats?.solved_by_difficulty?.find(d => d.difficulty === 'easy')?.count || 0;
  const medSolved = stats?.solved_by_difficulty?.find(d => d.difficulty === 'medium')?.count || 0;
  const hardSolved = stats?.solved_by_difficulty?.find(d => d.difficulty === 'hard')?.count || 0;
  const totalSolved = stats?.total_solved || 0;
  const weeklySolved = stats?.weekly_solved || 0;
  const topPatterns = (stats?.solved_by_pattern || []).slice(0, 3);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-40" />
            <Skeleton className="h-4 w-72 mt-2" />
          </div>
          <Skeleton className="h-9 w-32 rounded-lg" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <Skeleton className="h-48 w-full rounded-2xl" />
            <Skeleton className="h-80 w-full rounded-2xl" />
          </div>
          <div className="space-y-6">
            <Skeleton className="h-64 w-full rounded-2xl" />
            <Skeleton className="h-40 w-full rounded-2xl" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="DSA PREP"
        title="DSA Prep"
        subtitle="Track your problem-solving progress and stay interview-ready."
        actions={
          <Button variant={showAdd ? 'secondary' : 'accent'} onClick={() => setShowAdd(!showAdd)}>
            {showAdd ? 'Cancel' : '+ Add Problem'}
          </Button>
        }
      />

      {/* Add Problem Form */}
      {showAdd && (
        <Card>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-dark-300 mb-1">Title</label>
                <input
                  value={newProblem.title}
                  onChange={e => setNewProblem(p => ({ ...p, title: e.target.value }))}
                  className="w-full bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="e.g. Two Sum"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-dark-300 mb-1">Difficulty</label>
                <select
                  value={newProblem.difficulty}
                  onChange={e => setNewProblem(p => ({ ...p, difficulty: e.target.value }))}
                  className="w-full bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-dark-300 mb-1">Pattern</label>
                <select
                  value={newProblem.pattern}
                  onChange={e => setNewProblem(p => ({ ...p, pattern: e.target.value }))}
                  className="w-full bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {PATTERNS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-dark-300 mb-1">LeetCode URL (optional)</label>
                <input
                  value={newProblem.leetcode_url}
                  onChange={e => setNewProblem(p => ({ ...p, leetcode_url: e.target.value }))}
                  className="w-full bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="https://leetcode.com/problems/..."
                />
              </div>
              <div>
                <label className="block text-sm text-dark-300 mb-1">Notes (optional)</label>
                <input
                  value={newProblem.notes}
                  onChange={e => setNewProblem(p => ({ ...p, notes: e.target.value }))}
                  className="w-full bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="Key insight, time complexity, etc."
                />
              </div>
            </div>
            <Button variant="primary" type="submit" loading={saving}>Add Problem</Button>
          </form>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Difficulty Progress */}
          <Card>
            <div className="flex items-center justify-between mb-6">
              <h2 className="font-display text-xl text-dark-50">Problem Progress</h2>
              <div className="text-sm text-dark-400 tabular-nums">{totalSolved} solved</div>
            </div>
            <div className="grid grid-cols-3 gap-4 mb-6">
              {[
                { label: 'Easy', count: easySolved, color: DIFFICULTY_COLORS.easy },
                { label: 'Medium', count: medSolved, color: DIFFICULTY_COLORS.medium },
                { label: 'Hard', count: hardSolved, color: DIFFICULTY_COLORS.hard },
              ].map(d => (
                <div key={d.label} className="text-center">
                  <div className="font-display tabular-nums text-4xl" style={{ color: d.color }}>{d.count}</div>
                  <div className="text-xs uppercase tracking-wider text-dark-400 mt-1">{d.label}</div>
                </div>
              ))}
            </div>
            {totalSolved > 0 && (
              <ProgressBar
                value={Math.min(100, (totalSolved / Math.max(stats?.total_problems || 1, 1)) * 100)}
                label={`${totalSolved} / ${stats?.total_problems || 0} total`}
              />
            )}
          </Card>

          {/* Problem List */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-xl text-dark-50">Problems</h2>
              <select
                value={patternFilter}
                onChange={e => setPatternFilter(e.target.value)}
                className="bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="all">All Patterns</option>
                {PATTERNS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>

            {filteredProblems.length === 0 ? (
              problems.length === 0 ? (
                <div className="text-center py-10">
                  <p className="font-display text-2xl text-dark-50">No problems tracked yet</p>
                  <p className="text-dark-400 text-sm mt-2 max-w-xs mx-auto">
                    Log the problems you grind through and watch your patterns and streak build up over the weeks.
                  </p>
                  {!showAdd && (
                    <Button variant="accent" className="mt-5" onClick={() => setShowAdd(true)}>
                      Add your first problem
                    </Button>
                  )}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-dark-400">No problems match this filter.</p>
                </div>
              )
            ) : (
              <div className="space-y-2">
                {filteredProblems.map(problem => (
                  <div
                    key={problem.id}
                    className="flex items-center gap-3 p-3 bg-dark-800/50 border border-dark-700 rounded-lg hover:border-dark-500 transition-colors"
                  >
                    {/* Difficulty dot */}
                    <div
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: DIFFICULTY_COLORS[problem.difficulty] }}
                      title={problem.difficulty}
                    />

                    {/* Title + pattern */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {safeExternalUrl(problem.leetcode_url) ? (
                          <a
                            href={safeExternalUrl(problem.leetcode_url)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-white hover:text-primary-400 transition-colors truncate"
                          >
                            {problem.title}
                          </a>
                        ) : (
                          <span className="text-sm font-medium text-white truncate">{problem.title}</span>
                        )}
                        <span className="flex-shrink-0">
                          <Badge color="gray" variant="label">{problem.pattern}</Badge>
                        </span>
                      </div>
                      {problem.notes && (
                        <p className="text-xs text-dark-500 mt-0.5 truncate">{problem.notes}</p>
                      )}
                    </div>

                    {/* Status */}
                    <select
                      value={problem.status}
                      onChange={e => handleStatusChange(problem, e.target.value)}
                      className={`text-xs rounded-lg px-2 py-1 border focus:outline-none focus:ring-1 focus:ring-primary-500 ${
                        problem.status === 'solved'
                          ? 'bg-green-500/10 border-green-500/30 text-green-400'
                          : problem.status === 'attempted'
                          ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                          : 'bg-dark-700 border-dark-600 text-dark-400'
                      }`}
                    >
                      <option value="not_started">Not Started</option>
                      <option value="attempted">Attempted</option>
                      <option value="solved">Solved</option>
                    </select>

                    {/* Mark Solved button */}
                    {problem.status !== 'solved' && (
                      <button
                        onClick={() => handleMarkSolved(problem)}
                        className="text-xs text-green-400 hover:text-green-300 transition-colors px-2 py-1 rounded-lg hover:bg-green-500/10 flex-shrink-0"
                        title="Mark as solved"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </button>
                    )}

                    {/* Delete */}
                    <button
                      onClick={() => handleDelete(problem.id)}
                      className="text-xs text-dark-500 hover:text-red-400 transition-colors p-1 flex-shrink-0"
                      title="Delete"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Weekly Goal */}
          <Card>
            <h2 className="font-display text-xl text-dark-50 mb-4">Weekly Goal</h2>
            <div className="flex flex-col items-center">
              <ProgressRing
                value={Math.min(100, (weeklySolved / weeklyGoal) * 100)}
                size={140}
                strokeWidth={10}
                label="this week"
              />
              <p className="mt-3 text-sm text-dark-400 tabular-nums">
                <span className="text-dark-50 font-semibold">{weeklySolved}</span> / {weeklyGoal} problems
              </p>
              <div className="flex items-center gap-2 mt-3">
                <label className="text-xs text-dark-400">Goal:</label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={weeklyGoal}
                  onChange={e => handleGoalChange(e.target.value)}
                  className="w-16 bg-dark-800 border border-dark-600 text-white rounded-lg px-2 py-1 text-sm text-center focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <span className="text-xs text-dark-400">/week</span>
              </div>
            </div>
          </Card>

          {/* Stats */}
          <Card>
            <h2 className="font-display text-xl text-dark-50 mb-4">Stats</h2>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-dark-400">Total Solved</span>
                <span className="text-dark-50 font-semibold tabular-nums">{totalSolved}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-dark-400">Total Problems</span>
                <span className="text-dark-50 font-semibold tabular-nums">{stats?.total_problems || 0}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-dark-400">This Week</span>
                <span className="text-dark-50 font-semibold tabular-nums">{weeklySolved}</span>
              </div>
            </div>
          </Card>

          {/* Top Patterns */}
          {topPatterns.length > 0 && (
            <Card>
              <h2 className="font-display text-xl text-dark-50 mb-4">Top Patterns</h2>
              <div className="space-y-3">
                {topPatterns.map((p, i) => (
                  <div key={p.pattern} className="flex items-center gap-3">
                    <span className="font-display text-sm text-primary-500 w-4 tabular-nums">{i + 1}</span>
                    <span className="text-sm text-dark-200 flex-1">{p.pattern}</span>
                    <span className="text-sm text-dark-50 font-semibold tabular-nums">{p.count}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
