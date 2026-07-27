import { useState } from 'react';
import Card from '../ui/Card';
import Skeleton from '../ui/Skeleton';
import { reviewResume } from '../../api/career';
import { getErrorMessage } from '../../utils/errors';

const scoreColor = (score) => {
  if (score >= 8) return 'text-green-400';
  if (score >= 6) return 'text-yellow-400';
  if (score >= 4) return 'text-orange-400';
  return 'text-red-400';
};

export default function ResumeReview() {
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = async (file) => {
    setLoading(true);
    setError(null);
    setReview(null);
    try {
      const res = await reviewResume(file);
      setReview(res.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to review document.'));
    } finally {
      setLoading(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const onFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) handleFile(file);
  };

  if (loading) {
    return (
      <Card>
        <div className="flex items-center gap-3 mb-5">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-500 flex-shrink-0" />
          <div>
            <p className="text-white text-sm font-medium">Analyzing your resume...</p>
            <p className="text-dark-400 text-xs mt-0.5">Your AI advisor is reviewing scoring, strengths, and ATS fit.</p>
          </div>
        </div>

        {/* Skeleton preview of the review layout */}
        <div className="flex items-center gap-4 mb-5">
          <Skeleton className="h-12 w-12 flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        </div>
        <div className="space-y-2 mb-5">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-11/12" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-16 w-full" />
        </div>
      </Card>
    );
  }

  if (review) {
    return (
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold">Resume Review</h3>
          <button
            onClick={() => setReview(null)}
            className="text-dark-400 hover:text-white text-sm transition-colors"
          >
            Upload another
          </button>
        </div>

        {/* Score + Summary */}
        <div className="flex items-center gap-4 mb-4">
          {review.overall_score != null && (
            <div className="flex-shrink-0 text-center">
              <p className={`text-3xl font-bold ${scoreColor(review.overall_score)}`}>
                {review.overall_score}/10
              </p>
              <p className="text-dark-500 text-xs">Score</p>
            </div>
          )}
          <p className="text-dark-300 text-sm">{review.summary}</p>
        </div>

        {/* Strengths */}
        {review.strengths?.length > 0 && (
          <div className="mb-4">
            <h4 className="text-green-400 text-sm font-medium mb-2">Strengths</h4>
            <ul className="space-y-1">
              {review.strengths.map((s, i) => (
                <li key={i} className="text-dark-300 text-sm flex gap-2">
                  <span className="text-green-500 flex-shrink-0">+</span> {s}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Improvements */}
        {review.improvements?.length > 0 && (
          <div className="mb-4">
            <h4 className="text-yellow-400 text-sm font-medium mb-2">Areas for Improvement</h4>
            <div className="space-y-2">
              {review.improvements.map((imp, i) => (
                <div key={i} className="bg-dark-700/50 rounded-lg p-3">
                  <p className="text-white text-sm font-medium">{imp.area}</p>
                  <p className="text-dark-400 text-xs mt-0.5">{imp.issue}</p>
                  <p className="text-primary-400 text-xs mt-1">{imp.suggestion}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Missing Sections */}
        {review.missing_sections?.length > 0 && (
          <div className="mb-4">
            <h4 className="text-orange-400 text-sm font-medium mb-2">Missing Sections</h4>
            <div className="flex flex-wrap gap-2">
              {review.missing_sections.map((s, i) => (
                <span key={i} className="text-xs bg-orange-500/10 text-orange-300 rounded-full px-2.5 py-1">
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* ATS Tips */}
        {review.ats_tips?.length > 0 && (
          <div className="mb-4">
            <h4 className="text-primary-400 text-sm font-medium mb-2">ATS Optimization Tips</h4>
            <ul className="space-y-1">
              {review.ats_tips.map((t, i) => (
                <li key={i} className="text-dark-300 text-sm flex gap-2">
                  <span className="text-primary-500 flex-shrink-0">*</span> {t}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Tailored Advice */}
        {review.tailored_advice && (
          <div className="bg-primary-500/5 border border-dark-600 rounded-lg p-3">
            <h4 className="text-primary-400 text-sm font-medium mb-1">Tailored Advice</h4>
            <p className="text-dark-300 text-sm">{review.tailored_advice}</p>
          </div>
        )}
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="text-white font-semibold mb-3">Resume / Cover Letter Review</h3>
      {error && <p className="text-red-400 text-sm mb-3">{error}</p>}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
          dragOver ? 'border-primary-500 bg-primary-500/5' : 'border-dark-600 hover:border-dark-500'
        }`}
        onClick={() => document.getElementById('resume-upload').click()}
      >
        <svg className="w-10 h-10 mx-auto text-dark-500 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12l-3-3m0 0l-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
        <p className="text-dark-300 text-sm">Drop your resume or cover letter here</p>
        <p className="text-dark-500 text-xs mt-1">PDF or image, max 10MB</p>
        <input
          id="resume-upload"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          onChange={onFileSelect}
          className="hidden"
        />
      </div>
    </Card>
  );
}
