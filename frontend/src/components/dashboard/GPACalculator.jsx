import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../../context/AuthContext';
import { getGPA } from '../../api/degree';
import { getScale, buildGradeMap } from '../../data/gradingScales';
import Card from '../ui/Card';
import Badge from '../ui/Badge';
import ProgressRing from '../ui/ProgressRing';
import Button from '../ui/Button';

export default function GPACalculator({ compact = false, bento = false }) {
  const { user } = useAuth();
  const [gpa, setGpa] = useState(null);
  const [loading, setLoading] = useState(true);
  const [whatIfOpen, setWhatIfOpen] = useState(false);
  const [whatIfCourses, setWhatIfCourses] = useState([]);

  const { scale, isFallback } = useMemo(() => getScale(user?.university), [user?.university]);
  const gradeMap = useMemo(() => buildGradeMap(scale), [scale]);

  useEffect(() => {
    getGPA()
      .then(res => setGpa(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // What-if projected GPA
  const projectedGPA = useMemo(() => {
    if (!gpa) return null;
    let totalPoints = (gpa.cumulative_gpa || 0) * gpa.total_credits_completed;
    let totalCredits = gpa.total_credits_completed;
    for (const c of whatIfCourses) {
      const pts = gradeMap[c.grade?.toUpperCase()];
      if (pts !== undefined && c.credits > 0) {
        totalPoints += pts * c.credits;
        totalCredits += c.credits;
      }
    }
    return totalCredits > 0 ? (totalPoints / totalCredits).toFixed(2) : null;
  }, [gpa, whatIfCourses, gradeMap]);

  function addWhatIfCourse() {
    setWhatIfCourses(prev => [...prev, { name: '', credits: 0.5, grade: scale.grades[0]?.letter || 'A' }]);
  }

  function updateWhatIfCourse(index, field, value) {
    setWhatIfCourses(prev => prev.map((c, i) => i === index ? { ...c, [field]: value } : c));
  }

  function removeWhatIfCourse(index) {
    setWhatIfCourses(prev => prev.filter((_, i) => i !== index));
  }

  function tierColor(val, max) {
    const pct = val / max;
    if (pct >= 0.75) return 'green';
    if (pct >= 0.50) return 'yellow';
    return 'red';
  }

  if (loading) {
    if (bento) return <div className="flex items-center justify-center h-full"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-500" /></div>;
    return (
      <Card>
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-500" />
        </div>
      </Card>
    );
  }

  // Compact card variant for the dashboard grid
  if (compact) {
    if (!gpa || gpa.cumulative_gpa === null) {
      if (bento) return <div><h3 className="text-white font-semibold mb-2">GPA</h3><p className="text-dark-400 text-sm">No graded courses yet.</p></div>;
      return (
        <Card>
          <h3 className="text-white font-semibold mb-2">GPA</h3>
          <p className="text-dark-400 text-sm">No graded courses yet.</p>
        </Card>
      );
    }
    const pct = (gpa.cumulative_gpa / gpa.scale_max) * 100;
    const color = tierColor(gpa.cumulative_gpa, gpa.scale_max);
    const textColor = color === 'green' ? 'text-green-400' : color === 'yellow' ? 'text-yellow-400' : 'text-red-400';

    const content = (
      <>
        <h3 className="text-white font-semibold mb-3">GPA</h3>
        <div className="flex items-end gap-4 mb-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-dark-400">Cumulative</p>
            <p className={`font-display tabular-nums text-3xl sm:text-4xl mt-1 ${textColor}`}>
              {gpa.cumulative_gpa.toFixed(2)}
              <span className="text-base text-dark-500 font-normal"> / {gpa.scale_max}</span>
            </p>
          </div>
          {gpa.term_gpas.length > 1 && (
            <div className="flex-1 flex items-end gap-1 h-16">
              {gpa.term_gpas.map((t, i) => {
                const height = Math.max((t.gpa / gpa.scale_max) * 100, 10);
                const barColor = tierColor(t.gpa, gpa.scale_max);
                const bgClass = barColor === 'green' ? 'bg-green-500' : barColor === 'yellow' ? 'bg-yellow-500' : 'bg-red-500';
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1" title={`${t.term}: ${t.gpa.toFixed(2)}`}>
                    <div className={`w-full rounded-sm ${bgClass}`} style={{ height: `${height}%` }} />
                    <span className="text-dark-500 text-[9px] truncate w-full text-center">{t.term.split(' ').pop()}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        <p className="text-dark-500 text-xs">{gpa.scale_name}</p>
        {gpa.using_fallback && (
          <p className="text-yellow-400/80 text-[10px] mt-1">Using standard 4.0 scale</p>
        )}
      </>
    );

    if (bento) return <div>{content}</div>;
    return <Card>{content}</Card>;
  }

  // Full GPA view for the DegreePage tab
  return (
    <div className="space-y-6">
      {/* Main GPA Card */}
      <Card gradient>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">GPA Overview</h2>
          <div className="text-sm text-dark-400">{gpa?.scale_name}</div>
        </div>

        {gpa?.using_fallback && (
          <div className="mb-4 flex items-center gap-2">
            <Badge color="yellow">Fallback Scale</Badge>
            <span className="text-dark-400 text-xs">Your university's exact scale is not yet in our system</span>
          </div>
        )}

        {gpa?.cumulative_gpa === null ? (
          <div className="text-center py-8">
            <p className="text-dark-400">No graded courses yet.</p>
            <p className="text-dark-500 text-sm mt-1">Add completed courses with grades to see your GPA.</p>
          </div>
        ) : (
          <div className="flex items-center gap-8">
            <ProgressRing
              value={(gpa.cumulative_gpa / gpa.scale_max) * 100}
              size={140}
              strokeWidth={10}
              label={`/ ${gpa.scale_max}`}
            />
            <div className="space-y-3 flex-1">
              <div className="flex justify-between text-sm">
                <span className="text-dark-400">Cumulative GPA</span>
                <span className="text-white font-bold text-lg">{gpa.cumulative_gpa.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-dark-400">Graded Courses</span>
                <span className="text-white font-semibold">{gpa.graded_course_count}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-dark-400">Total Credits</span>
                <span className="text-white font-semibold">{gpa.total_credits_completed}</span>
              </div>
              {gpa.highest_term && gpa.lowest_term && gpa.highest_term.term !== gpa.lowest_term.term && (
                <>
                  <div className="flex justify-between text-sm">
                    <span className="text-dark-400">Best Term</span>
                    <span className="text-green-400 font-semibold">{gpa.highest_term.term} ({gpa.highest_term.gpa.toFixed(2)})</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-dark-400">Lowest Term</span>
                    <span className="text-red-400 font-semibold">{gpa.lowest_term.term} ({gpa.lowest_term.gpa.toFixed(2)})</span>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </Card>

      {/* Term Breakdown */}
      {gpa?.term_gpas?.length > 0 && (
        <Card>
          <h2 className="text-lg font-semibold text-white mb-4">Term Breakdown</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-700">
                  <th className="text-left text-dark-400 text-xs font-medium px-4 py-2">Term</th>
                  <th className="text-left text-dark-400 text-xs font-medium px-4 py-2">GPA</th>
                  <th className="text-left text-dark-400 text-xs font-medium px-4 py-2">Courses</th>
                  <th className="text-left text-dark-400 text-xs font-medium px-4 py-2">Credits</th>
                  <th className="text-left text-dark-400 text-xs font-medium px-4 py-2">Standing</th>
                </tr>
              </thead>
              <tbody>
                {gpa.term_gpas.map((t) => {
                  const color = tierColor(t.gpa, gpa.scale_max);
                  const isHighest = gpa.highest_term?.term === t.term && gpa.term_gpas.length > 1;
                  const isLowest = gpa.lowest_term?.term === t.term && gpa.term_gpas.length > 1;
                  return (
                    <tr key={t.term} className="border-b border-dark-700/50 last:border-0">
                      <td className="px-4 py-2.5 text-white text-sm font-medium">
                        {t.term}
                        {isHighest && <span className="ml-2 text-green-400 text-xs">Best</span>}
                        {isLowest && <span className="ml-2 text-red-400 text-xs">Lowest</span>}
                      </td>
                      <td className="px-4 py-2.5 text-white text-sm font-semibold">{t.gpa.toFixed(2)}</td>
                      <td className="px-4 py-2.5 text-dark-300 text-sm">{t.course_count}</td>
                      <td className="px-4 py-2.5 text-dark-300 text-sm">{t.credits}</td>
                      <td className="px-4 py-2.5"><Badge color={color}>{color === 'green' ? 'Good' : color === 'yellow' ? 'Fair' : 'Low'}</Badge></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* What-If Calculator */}
      <Card>
        <button
          onClick={() => setWhatIfOpen(!whatIfOpen)}
          className="flex items-center justify-between w-full text-left"
        >
          <h2 className="text-lg font-semibold text-white">What-If Calculator</h2>
          <svg className={`w-5 h-5 text-dark-400 transition-transform ${whatIfOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {whatIfOpen && (
          <div className="mt-4 space-y-4">
            <p className="text-dark-400 text-sm">Add hypothetical courses to see how they'd affect your GPA.</p>

            {whatIfCourses.length > 0 && (
              <div className="space-y-2">
                {whatIfCourses.map((c, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <input
                      value={c.name}
                      onChange={e => updateWhatIfCourse(i, 'name', e.target.value)}
                      className="flex-1 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                      placeholder="Course name"
                    />
                    <input
                      type="number"
                      step="0.25"
                      min="0"
                      value={c.credits}
                      onChange={e => updateWhatIfCourse(i, 'credits', parseFloat(e.target.value) || 0)}
                      className="w-20 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <select
                      value={c.grade}
                      onChange={e => updateWhatIfCourse(i, 'grade', e.target.value)}
                      className="w-24 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                    >
                      {scale.grades.map(g => (
                        <option key={g.letter} value={g.letter}>{g.letter} ({g.points})</option>
                      ))}
                    </select>
                    <button onClick={() => removeWhatIfCourse(i)} className="text-dark-400 hover:text-red-400 transition-colors">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}

            <Button variant="secondary" onClick={addWhatIfCourse}>+ Add Course</Button>

            {projectedGPA !== null && whatIfCourses.length > 0 && (
              <div className="bg-dark-900/50 border border-dark-700 rounded-lg p-4 flex items-center justify-between">
                <div>
                  <p className="text-dark-400 text-xs">Projected Cumulative GPA</p>
                  <p className="text-white text-2xl font-bold">
                    {projectedGPA}
                    <span className="text-base text-dark-500 font-normal"> / {gpa?.scale_max || scale.maxPoints}</span>
                  </p>
                </div>
                {gpa?.cumulative_gpa !== null && (
                  <div className="text-right">
                    <p className="text-dark-400 text-xs">Change</p>
                    <p className={`text-lg font-semibold ${parseFloat(projectedGPA) >= gpa.cumulative_gpa ? 'text-green-400' : 'text-red-400'}`}>
                      {parseFloat(projectedGPA) >= gpa.cumulative_gpa ? '+' : ''}
                      {(parseFloat(projectedGPA) - gpa.cumulative_gpa).toFixed(2)}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
