import { useState, useEffect } from 'react';
import {
  listAssessments,
  createAssessment,
  updateAssessment,
  deleteAssessment,
  getGradeProjection,
} from '../../api/degree';
import { getErrorMessage } from '../../utils/errors';
import SyllabusUpload from './SyllabusUpload';

const categoryColors = {
  exam: 'bg-red-500/20 text-red-400 border-red-500/30',
  assignment: 'bg-primary-500/20 text-primary-400 border-primary-500/30',
  quiz: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  other: 'bg-dark-600 text-dark-300 border-dark-500',
};

const categoryIcons = {
  exam: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
  assignment: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
  quiz: 'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  other: 'M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z',
};

const categoryOptions = ['exam', 'assignment', 'quiz', 'other'];

function formatDate(dateStr) {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function daysUntil(dateStr) {
  if (!dateStr) return null;
  return Math.ceil((new Date(dateStr) - new Date()) / (1000 * 60 * 60 * 24));
}

export default function AssessmentsPanel({ course }) {
  const [assessments, setAssessments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');

  const [projection, setProjection] = useState(null);
  const [target, setTarget] = useState('');

  const [newAssessment, setNewAssessment] = useState({
    title: '', weight: '', category: 'exam', score: '',
  });
  const [saving, setSaving] = useState(false);

  const fetchProjection = async (targetVal) => {
    try {
      const { data } = await getGradeProjection(course.id, targetVal);
      setProjection(data);
    } catch {
      setProjection(null);
    }
  };

  const fetchAssessments = async () => {
    setLoading(true);
    try {
      const { data } = await listAssessments(course.id);
      setAssessments(data);
      // Auto-show upload if no assessments exist
      if (data.length === 0) setShowUpload(true);
      else setShowUpload(false);
      await fetchProjection(target);
    } catch {
      setAssessments([]);
      setShowUpload(true);
      setProjection(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssessments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [course.id]);

  const handleParsed = () => {
    // Re-fetch from server to get the full merged list after multi-doc upload
    fetchAssessments();
  };

  const handleTargetChange = (e) => {
    const val = e.target.value;
    setTarget(val);
    fetchProjection(val);
  };

  const handleScoreSave = async (assessment, rawValue) => {
    const trimmed = rawValue.trim();
    const nextScore = trimmed === '' ? null : Number(trimmed);
    // No-op if unchanged
    if (nextScore === assessment.score) return;
    if (nextScore !== null && (Number.isNaN(nextScore) || nextScore < 0 || nextScore > 100)) {
      setError('Score must be between 0 and 100.');
      return;
    }
    setError('');
    try {
      await updateAssessment(assessment.id, { score: nextScore });
      const { data } = await listAssessments(course.id);
      setAssessments(data);
      await fetchProjection(target);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to save score.'));
    }
  };

  const handleDelete = async (assessment) => {
    setError('');
    try {
      await deleteAssessment(assessment.id);
      setAssessments((prev) => prev.filter((a) => a.id !== assessment.id));
      await fetchProjection(target);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to delete assessment.'));
    }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newAssessment.title.trim()) {
      setError('Title is required.');
      return;
    }
    setError('');
    setSaving(true);
    try {
      await createAssessment(course.id, {
        title: newAssessment.title.trim(),
        weight: newAssessment.weight === '' ? 0 : Number(newAssessment.weight),
        category: newAssessment.category,
        score: newAssessment.score === '' ? null : Number(newAssessment.score),
      });
      setNewAssessment({ title: '', weight: '', category: 'exam', score: '' });
      setShowAdd(false);
      await fetchAssessments();
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to add assessment.'));
    } finally {
      setSaving(false);
    }
  };

  const totalWeight = assessments.reduce((sum, a) => sum + a.weight, 0);
  const sorted = [...assessments].sort((a, b) => {
    if (!a.due_date && !b.due_date) return 0;
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return new Date(a.due_date) - new Date(b.due_date);
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h4 className="text-white font-medium">
            {course.course_code} — Assessments
          </h4>
          <span className="text-dark-400 text-sm">
            {assessments.length} item{assessments.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setShowAdd(!showAdd); setError(''); }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-dark-700 hover:bg-dark-600 text-white text-xs font-medium rounded-lg transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add
          </button>
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-600 hover:bg-primary-700 text-white text-xs font-medium rounded-lg transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            {assessments.length > 0 ? 'Re-parse Syllabus' : 'Upload Syllabus'}
          </button>
        </div>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {/* Grade projection summary */}
      {projection && projection.total_weight > 0 && (
        <div className="bg-dark-900/50 border border-dark-700 rounded-lg p-4 space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <p className="text-dark-500 text-[11px] uppercase tracking-wide">Current Standing</p>
              <p className="text-white text-lg font-semibold">
                {projection.current_weighted_pct != null ? `${projection.current_weighted_pct}%` : '—'}
              </p>
              <p className="text-dark-500 text-[10px]">on {projection.graded_weight}% graded</p>
            </div>
            <div>
              <p className="text-dark-500 text-[11px] uppercase tracking-wide">Projected Final</p>
              <p className="text-white text-lg font-semibold">
                {projection.projected_final_pct != null ? `${projection.projected_final_pct}%` : '—'}
              </p>
              <p className="text-dark-500 text-[10px]">if pace maintained</p>
            </div>
            <div>
              <p className="text-dark-500 text-[11px] uppercase tracking-wide">Letter</p>
              <p className="text-primary-400 text-lg font-semibold">
                {projection.projected_letter || '—'}
              </p>
            </div>
            <div>
              <p className="text-dark-500 text-[11px] uppercase tracking-wide">GPA Points</p>
              <p className="text-primary-400 text-lg font-semibold">
                {projection.projected_gpa_points != null ? projection.projected_gpa_points : '—'}
              </p>
              <p className="text-dark-500 text-[10px]">/ {projection.scale_max}</p>
            </div>
          </div>

          {/* Target planner */}
          <div className="border-t border-dark-700 pt-3">
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-dark-400 text-xs">Target final %</label>
              <input
                type="number"
                min="0"
                max="100"
                value={target}
                onChange={handleTargetChange}
                placeholder="e.g. 85"
                className="w-20 bg-dark-800 border border-dark-600 rounded-md px-2 py-1 text-white text-sm focus:outline-none focus:border-primary-500"
              />
              {target !== '' && projection.target_final_pct != null && (
                <span className="text-sm">
                  {projection.remaining_weight <= 0 ? (
                    projection.target_already_secured ? (
                      <span className="text-green-400">Already secured — no graded work remains.</span>
                    ) : (
                      <span className="text-red-400">Out of reach — no graded work remains.</span>
                    )
                  ) : projection.target_already_secured ? (
                    <span className="text-green-400">Already secured with your logged scores.</span>
                  ) : projection.target_achievable ? (
                    <span className="text-dark-200">
                      Need <span className="text-green-400 font-semibold">{projection.score_needed_on_remaining}%</span> avg
                      on the remaining {projection.remaining_weight}%.
                    </span>
                  ) : (
                    <span className="text-red-400">
                      Not achievable — would need {projection.score_needed_on_remaining}% on the remaining {projection.remaining_weight}%.
                    </span>
                  )}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Grade weight progress bar */}
      {assessments.length > 0 && (
        <div className="bg-dark-900/50 border border-dark-700 rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-dark-400 text-xs">Grade Weight Coverage</span>
            <span className={`text-sm font-semibold ${totalWeight >= 99 ? 'text-green-400' : totalWeight >= 80 ? 'text-yellow-400' : 'text-red-400'}`}>
              {totalWeight.toFixed(1)}%
            </span>
          </div>
          <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${totalWeight >= 99 ? 'bg-green-500' : totalWeight >= 80 ? 'bg-yellow-500' : 'bg-red-500'}`}
              style={{ width: `${Math.min(totalWeight, 100)}%` }}
            />
          </div>
          {totalWeight < 99 && (
            <p className="text-dark-500 text-xs mt-1">
              {(100 - totalWeight).toFixed(1)}% of grade weight not yet accounted for
            </p>
          )}
        </div>
      )}

      {/* Manual add form */}
      {showAdd && (
        <form onSubmit={handleAdd} className="bg-dark-800 border border-dark-700 rounded-lg p-3 space-y-2">
          <div className="flex flex-wrap gap-2">
            <input
              type="text"
              value={newAssessment.title}
              onChange={(e) => setNewAssessment({ ...newAssessment, title: e.target.value })}
              placeholder="Title (e.g. Midterm)"
              className="flex-1 min-w-[140px] bg-dark-900 border border-dark-600 rounded-md px-2 py-1.5 text-white text-sm focus:outline-none focus:border-primary-500"
            />
            <input
              type="number"
              min="0"
              max="100"
              value={newAssessment.weight}
              onChange={(e) => setNewAssessment({ ...newAssessment, weight: e.target.value })}
              placeholder="Weight %"
              className="w-24 bg-dark-900 border border-dark-600 rounded-md px-2 py-1.5 text-white text-sm focus:outline-none focus:border-primary-500"
            />
            <input
              type="number"
              min="0"
              max="100"
              value={newAssessment.score}
              onChange={(e) => setNewAssessment({ ...newAssessment, score: e.target.value })}
              placeholder="Score %"
              className="w-24 bg-dark-900 border border-dark-600 rounded-md px-2 py-1.5 text-white text-sm focus:outline-none focus:border-primary-500"
            />
            <select
              value={newAssessment.category}
              onChange={(e) => setNewAssessment({ ...newAssessment, category: e.target.value })}
              className="bg-dark-900 border border-dark-600 rounded-md px-2 py-1.5 text-white text-sm focus:outline-none focus:border-primary-500"
            >
              {categoryOptions.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={saving}
              className="px-3 py-1.5 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors"
            >
              {saving ? 'Adding…' : 'Add assessment'}
            </button>
            <button
              type="button"
              onClick={() => { setShowAdd(false); setError(''); }}
              className="px-3 py-1.5 text-dark-400 hover:text-white text-xs transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Upload zone */}
      {showUpload && (
        <SyllabusUpload courseId={course.id} onParsed={handleParsed} />
      )}

      {/* Assessment list */}
      {sorted.length > 0 ? (
        <div className="space-y-2">
          {sorted.map(a => {
            const days = daysUntil(a.due_date);
            const isPast = days !== null && days < 0;
            const isUrgent = days !== null && days >= 0 && days <= 7;
            return (
              <div
                key={a.id}
                className="flex items-center gap-3 bg-dark-800 border border-dark-700 rounded-lg px-4 py-3 hover:border-dark-600 transition-colors"
              >
                {/* Category icon */}
                <div className={`flex-shrink-0 w-8 h-8 rounded-lg border flex items-center justify-center ${categoryColors[a.category] || categoryColors.other}`}>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={categoryIcons[a.category] || categoryIcons.other} />
                  </svg>
                </div>

                {/* Title + notes */}
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-medium truncate">{a.title}</p>
                  {a.notes && <p className="text-dark-400 text-xs truncate">{a.notes}</p>}
                </div>

                {/* Score input */}
                <div className="flex-shrink-0 flex items-center gap-1">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    defaultValue={a.score ?? ''}
                    key={`${a.id}-${a.score}`}
                    onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); }}
                    onBlur={(e) => handleScoreSave(a, e.target.value)}
                    placeholder="—"
                    title="Score earned (%)"
                    className="w-16 bg-dark-900 border border-dark-600 rounded-md px-2 py-1 text-white text-sm text-right focus:outline-none focus:border-primary-500"
                  />
                  <span className="text-dark-500 text-xs">%</span>
                </div>

                {/* Weight */}
                <div className="flex-shrink-0 w-16 text-right">
                  <span className="text-dark-300 text-xs">wt {a.weight}%</span>
                </div>

                {/* Due date */}
                <div className="flex-shrink-0 w-24 text-right">
                  {a.due_date ? (
                    <div>
                      <p className={`text-xs font-medium ${isPast ? 'text-dark-500' : isUrgent ? 'text-red-400' : 'text-dark-300'}`}>
                        {formatDate(a.due_date)}
                      </p>
                      {days !== null && (
                        <p className={`text-[10px] ${isPast ? 'text-dark-500' : isUrgent ? 'text-red-400' : 'text-dark-500'}`}>
                          {isPast ? `${Math.abs(days)}d ago` : days === 0 ? 'Today' : `${days}d left`}
                        </p>
                      )}
                    </div>
                  ) : (
                    <span className="text-dark-500 text-xs">No date</span>
                  )}
                </div>

                {/* Delete */}
                <button
                  onClick={() => handleDelete(a)}
                  title="Delete assessment"
                  className="flex-shrink-0 text-dark-500 hover:text-red-400 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            );
          })}
        </div>
      ) : !showUpload && !showAdd ? (
        <div className="text-center py-8 bg-dark-800 border border-dark-700 rounded-lg">
          <svg className="w-10 h-10 text-dark-500 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-dark-400 text-sm">No assessments found for this course.</p>
          <p className="text-dark-500 text-xs mt-1">Upload a syllabus to auto-extract, or add one manually.</p>
        </div>
      ) : null}
    </div>
  );
}
