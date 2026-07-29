import { useEffect, useMemo, useState } from 'react';
import { getGPA, getGPAGoal, getGPAGoalMajor } from '../../api/degree';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

// Semantic GPA tiers — same 0.75 / 0.50 thresholds as GPACalculator/GPATracker.
function tier(value, max) {
  const pct = max > 0 ? value / max : 0;
  if (pct >= 0.75) return { name: 'green', color: '#22c55e' };
  if (pct >= 0.5) return { name: 'yellow', color: '#eab308' };
  return { name: 'red', color: '#ef4444' };
}

const PRIMARY = '#FFA22E'; // primary-400
const GATE_COLOR = '#eab308'; // yellow-500

// ── Inline-SVG term-over-term trend chart ────────────────────────────
function TrendChart({ termGpas, scaleMax, cumulativeGpa, gate }) {
  const W = 720;
  const H = 280;
  const PAD = { top: 20, right: 56, bottom: 36, left: 40 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const n = termGpas.length;

  const xFor = (i) => PAD.left + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const yFor = (v) => PAD.top + innerH - (Math.min(v, scaleMax) / scaleMax) * innerH;

  const points = termGpas.map((t, i) => ({ x: xFor(i), y: yFor(t.gpa), ...t }));
  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const areaPath = n
    ? `${linePath} L${points[n - 1].x.toFixed(1)} ${(PAD.top + innerH).toFixed(1)} L${points[0].x.toFixed(1)} ${(PAD.top + innerH).toFixed(1)} Z`
    : '';

  // Horizontal gridlines at 0 / 25 / 50 / 75 / 100 % of scale.
  const gridVals = [0, 0.25, 0.5, 0.75, 1].map((f) => +(f * scaleMax).toFixed(2));

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Term GPA trend">
        <defs>
          <linearGradient id="gpaArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={PRIMARY} stopOpacity="0.28" />
            <stop offset="100%" stopColor={PRIMARY} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Y gridlines + labels */}
        {gridVals.map((v) => {
          const y = yFor(v);
          return (
            <g key={v}>
              <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke="var(--color-dark-600)" strokeWidth="1" strokeDasharray="2 4" opacity="0.6" />
              <text x={PAD.left - 8} y={y + 3} textAnchor="end" fontSize="10" fill="var(--color-dark-400)">{v}</text>
            </g>
          );
        })}

        {/* Gate reference line (e.g. 4.50 EECS-major gate) */}
        {gate != null && gate <= scaleMax && (
          <g>
            <line x1={PAD.left} y1={yFor(gate)} x2={W - PAD.right} y2={yFor(gate)} stroke={GATE_COLOR} strokeWidth="1.5" strokeDasharray="5 4" opacity="0.9" />
            <text x={W - PAD.right + 4} y={yFor(gate) + 3} fontSize="10" fill={GATE_COLOR}>Gate {gate}</text>
          </g>
        )}

        {/* Cumulative reference line */}
        {cumulativeGpa != null && (
          <g>
            <line x1={PAD.left} y1={yFor(cumulativeGpa)} x2={W - PAD.right} y2={yFor(cumulativeGpa)} stroke={PRIMARY} strokeWidth="1.5" strokeDasharray="5 4" opacity="0.8" />
            <text x={W - PAD.right + 4} y={yFor(cumulativeGpa) + 3} fontSize="10" fill={PRIMARY}>Cum {cumulativeGpa.toFixed(2)}</text>
          </g>
        )}

        {/* Area + line */}
        {n > 0 && <path d={areaPath} fill="url(#gpaArea)" stroke="none" />}
        {n > 1 && <path d={linePath} fill="none" stroke={PRIMARY} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />}

        {/* Points + x labels */}
        {points.map((p, i) => {
          const c = tier(p.gpa, scaleMax).color;
          return (
            <g key={i}>
              <circle cx={p.x} cy={p.y} r="4.5" fill={c} stroke="var(--color-dark-800)" strokeWidth="2" />
              <title>{`${p.term}: ${p.gpa.toFixed(2)}`}</title>
              <text x={p.x} y={PAD.top + innerH + 18} textAnchor="middle" fontSize="10" fill="var(--color-dark-400)">
                {p.term.length > 10 ? p.term.split(' ').slice(-2).join(' ') : p.term}
              </text>
              <text x={p.x} y={p.y - 10} textAnchor="middle" fontSize="10" fontWeight="600" fill="var(--color-dark-300)">
                {p.gpa.toFixed(2)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Shared result panel for a goal projection ────────────────────────
function GoalResult({ goal, label }) {
  if (!goal) return null;
  const { needed_average, achievable, already_met, scale_max } = goal;

  let state, badge, textColor;
  if (already_met) {
    state = 'Already secured';
    badge = 'green';
    textColor = 'text-green-400';
  } else if (!achievable) {
    state = 'Out of reach';
    badge = 'red';
    textColor = 'text-red-400';
  } else {
    state = 'Achievable';
    badge = 'blue';
    textColor = 'text-primary-400';
  }

  return (
    <div className="bg-dark-900/50 border border-dark-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-dark-400 text-xs">{label}</p>
        <Badge color={badge}>{state}</Badge>
      </div>
      {already_met ? (
        <p className={`text-2xl font-bold ${textColor}`}>You're already there</p>
      ) : (
        <p className={`text-3xl font-bold ${textColor}`}>
          {needed_average.toFixed(2)}
          <span className="text-base text-dark-500 font-normal"> / {scale_max}</span>
        </p>
      )}
      {!already_met && !achievable && (
        <p className="text-dark-400 text-xs mt-1">
          That exceeds the {scale_max} maximum on your scale — the target isn't reachable with this many credits remaining.
        </p>
      )}
    </div>
  );
}

const inputCls =
  'w-full bg-dark-900 border border-dark-600 text-white rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500';

export default function GPATrendGoal() {
  const [gpa, setGpa] = useState(null);
  const [loading, setLoading] = useState(true);

  // Cumulative goal calculator
  const [target, setTarget] = useState('');
  const [remaining, setRemaining] = useState('');
  const [goal, setGoal] = useState(null);
  const [goalErr, setGoalErr] = useState('');

  // Major-gate goal calculator
  const [majorRemaining, setMajorRemaining] = useState('6');
  const [majorGoal, setMajorGoal] = useState(null);

  const majorScope = useMemo(() => {
    const m = gpa?.major_gpas?.find((x) => x.credits > 0) || gpa?.major_gpas?.[0];
    return m?.scope || null;
  }, [gpa]);

  useEffect(() => {
    getGPA()
      .then((res) => setGpa(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Debounced cumulative goal fetch.
  useEffect(() => {
    const t = parseFloat(target);
    const r = parseFloat(remaining);
    setGoalErr('');
    if (target === '' || remaining === '' || Number.isNaN(t) || Number.isNaN(r)) {
      setGoal(null);
      return;
    }
    if (r <= 0) {
      setGoal(null);
      setGoalErr('Remaining credits must be greater than zero.');
      return;
    }
    const id = setTimeout(() => {
      getGPAGoal(t, r)
        .then((res) => setGoal(res.data))
        .catch(() => { setGoal(null); setGoalErr('Could not compute projection.'); });
    }, 300);
    return () => clearTimeout(id);
  }, [target, remaining]);

  // Debounced major-gate goal fetch (only when the student has a major scope).
  useEffect(() => {
    if (!majorScope) return;
    const r = parseFloat(majorRemaining);
    if (majorRemaining === '' || Number.isNaN(r) || r <= 0) {
      setMajorGoal(null);
      return;
    }
    const id = setTimeout(() => {
      getGPAGoalMajor(r, majorScope)
        .then((res) => setMajorGoal(res.data))
        .catch(() => setMajorGoal(null));
    }, 300);
    return () => clearTimeout(id);
  }, [majorRemaining, majorScope]);

  if (loading) {
    return (
      <Card>
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-500" />
        </div>
      </Card>
    );
  }

  const hasTrend = gpa?.term_gpas?.length > 0;
  const scaleMax = gpa?.scale_max || 4.0;

  return (
    <div className="space-y-6">
      {/* GPA Trend chart */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">GPA Trend</h2>
          <span className="text-dark-400 text-sm">{gpa?.scale_name}</span>
        </div>
        {hasTrend ? (
          <>
            <TrendChart
              termGpas={gpa.term_gpas}
              scaleMax={scaleMax}
              cumulativeGpa={gpa.cumulative_gpa}
              gate={majorGoal?.gate}
            />
            <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-dark-400">
              <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-0.5" style={{ background: PRIMARY }} /> Term GPA</span>
              <span className="flex items-center gap-1.5"><span className="inline-block w-3 border-t border-dashed" style={{ borderColor: PRIMARY }} /> Cumulative</span>
              {majorGoal?.gate != null && (
                <span className="flex items-center gap-1.5"><span className="inline-block w-3 border-t border-dashed" style={{ borderColor: GATE_COLOR }} /> {majorScope} gate ({majorGoal.gate})</span>
              )}
            </div>
          </>
        ) : (
          <p className="text-dark-400 text-sm text-center py-8">Add completed courses with grades across terms to see your GPA trend.</p>
        )}
      </Card>

      {/* Goal projection calculator */}
      <Card>
        <h2 className="text-lg font-semibold text-white mb-1">Goal Projection</h2>
        <p className="text-dark-400 text-sm mb-4">
          What average do you need on your remaining credits to hit a target cumulative GPA?
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-dark-400 text-xs mb-1.5">Target cumulative GPA (max {scaleMax})</label>
            <input
              type="number" step="0.1" min="0" max={scaleMax}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className={inputCls}
              placeholder={`e.g. ${(scaleMax * 0.8).toFixed(1)}`}
            />
          </div>
          <div>
            <label className="block text-dark-400 text-xs mb-1.5">Credits remaining until graduation</label>
            <input
              type="number" step="0.5" min="0"
              value={remaining}
              onChange={(e) => setRemaining(e.target.value)}
              className={inputCls}
              placeholder="e.g. 30"
            />
          </div>
        </div>
        {goalErr && <p className="text-red-400 text-sm mb-3">{goalErr}</p>}
        {goal ? (
          <GoalResult goal={goal} label="Required average on remaining credits" />
        ) : (
          !goalErr && <p className="text-dark-500 text-sm">Enter a target and remaining credits to see the average you'd need.</p>
        )}
      </Card>

      {/* Major-gate goal — only when the student has a gated major scope */}
      {majorScope && (
        <Card>
          <h2 className="text-lg font-semibold text-white mb-1">{majorScope}-Major Gate</h2>
          <p className="text-dark-400 text-sm mb-4">
            What average do you need on your next {majorScope} credits to clear the
            {majorGoal?.gate != null ? ` ${majorGoal.gate}` : ''} {majorScope}-major gate?
          </p>
          <div className="mb-4 max-w-xs">
            <label className="block text-dark-400 text-xs mb-1.5">Upcoming {majorScope} credits</label>
            <input
              type="number" step="0.5" min="0"
              value={majorRemaining}
              onChange={(e) => setMajorRemaining(e.target.value)}
              className={inputCls}
              placeholder="e.g. 6"
            />
          </div>
          {majorGoal && (
            <>
              <div className="flex flex-wrap gap-4 mb-3 text-sm">
                <span className="text-dark-400">Current {majorScope} GPA:
                  <span className="text-white font-semibold ml-1">
                    {majorGoal.current_major_gpa != null ? majorGoal.current_major_gpa.toFixed(2) : '—'}
                  </span>
                </span>
                <span className="text-dark-400">{majorScope} credits done:
                  <span className="text-white font-semibold ml-1">{majorGoal.major_credits_completed}</span>
                </span>
              </div>
              <GoalResult
                goal={majorGoal}
                label={`Required average on your next ${majorRemaining || 'N'} ${majorScope} credits`}
              />
            </>
          )}
        </Card>
      )}
    </div>
  );
}
