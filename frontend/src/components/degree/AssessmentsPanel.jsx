import { useState, useEffect } from 'react';
import { listAssessments } from '../../api/degree';
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

  const fetchAssessments = async () => {
    setLoading(true);
    try {
      const { data } = await listAssessments(course.id);
      setAssessments(data);
      // Auto-show upload if no assessments exist
      if (data.length === 0) setShowUpload(true);
      else setShowUpload(false);
    } catch {
      setAssessments([]);
      setShowUpload(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssessments();
  }, [course.id]);

  const handleParsed = () => {
    // Re-fetch from server to get the full merged list after multi-doc upload
    fetchAssessments();
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
      {/* Header with weight progress */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h4 className="text-white font-medium">
            {course.course_code} — Assessments
          </h4>
          <span className="text-dark-400 text-sm">
            {assessments.length} item{assessments.length !== 1 ? 's' : ''}
          </span>
        </div>
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

                {/* Weight */}
                <div className="flex-shrink-0 text-right">
                  <span className="text-white text-sm font-semibold">{a.weight}%</span>
                </div>

                {/* Due date */}
                <div className="flex-shrink-0 w-28 text-right">
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
              </div>
            );
          })}
        </div>
      ) : !showUpload ? (
        <div className="text-center py-8 bg-dark-800 border border-dark-700 rounded-lg">
          <svg className="w-10 h-10 text-dark-500 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-dark-400 text-sm">No assessments found for this course.</p>
          <p className="text-dark-500 text-xs mt-1">Upload a syllabus to auto-extract assessments.</p>
        </div>
      ) : null}
    </div>
  );
}
