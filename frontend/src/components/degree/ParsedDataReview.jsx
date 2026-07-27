import { useState } from 'react';
import Button from '../ui/Button';

export default function ParsedDataReview({ data, onConfirm, onCancel }) {
  const [requirements, setRequirements] = useState(data.requirements || []);
  const [courses, setCourses] = useState(data.courses || []);

  function updateReq(index, field, value) {
    setRequirements((prev) =>
      prev.map((r, i) => (i === index ? { ...r, [field]: value } : r))
    );
  }

  function removeReq(index) {
    setRequirements((prev) => prev.filter((_, i) => i !== index));
  }

  function updateCourse(index, field, value) {
    setCourses((prev) =>
      prev.map((c, i) => (i === index ? { ...c, [field]: value } : c))
    );
  }

  function removeCourse(index) {
    setCourses((prev) => prev.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">Review Parsed Data</h3>
        <p className="text-dark-400 text-sm">Edit any fields before saving. Remove rows you don't need.</p>
      </div>

      {/* Requirements */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-dark-300">
          Requirement Buckets ({requirements.length})
        </h4>
        {requirements.length === 0 && (
          <p className="text-dark-500 text-sm italic">No requirements found in document.</p>
        )}
        <div className="space-y-2">
          {requirements.map((req, i) => (
            <div key={i} className="flex gap-3 items-center bg-dark-900/50 border border-dark-700 rounded-lg p-3">
              <input
                value={req.bucket_name}
                onChange={(e) => updateReq(i, 'bucket_name', e.target.value)}
                className="flex-1 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                placeholder="Bucket name"
              />
              <input
                type="number"
                step="0.5"
                value={req.credits_required}
                onChange={(e) => updateReq(i, 'credits_required', parseFloat(e.target.value) || 0)}
                className="w-24 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                placeholder="Credits"
              />
              <button onClick={() => removeReq(i)} className="text-dark-400 hover:text-red-400 transition-colors">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Courses */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-dark-300">
          Courses ({courses.length})
        </h4>
        {courses.length === 0 && (
          <p className="text-dark-500 text-sm italic">No courses found in document.</p>
        )}
        <div className="max-h-80 overflow-y-auto space-y-2">
          {courses.map((course, i) => (
            <div key={i} className="bg-dark-900/50 border border-dark-700 rounded-lg p-3">
              <div className="flex gap-2 items-center flex-wrap">
                <input
                  value={course.course_code}
                  onChange={(e) => updateCourse(i, 'course_code', e.target.value)}
                  className="w-28 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                  placeholder="Code"
                />
                <input
                  value={course.course_name}
                  onChange={(e) => updateCourse(i, 'course_name', e.target.value)}
                  className="flex-1 min-w-[150px] bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                  placeholder="Course name"
                />
                <input
                  type="number"
                  step="0.25"
                  value={course.credit_value}
                  onChange={(e) => updateCourse(i, 'credit_value', parseFloat(e.target.value) || 0)}
                  className="w-20 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                  placeholder="Credits"
                />
                <select
                  value={course.requirement_bucket || ''}
                  onChange={(e) => updateCourse(i, 'requirement_bucket', e.target.value)}
                  className="w-36 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="">No bucket</option>
                  {requirements.map((r, ri) => (
                    <option key={ri} value={r.bucket_name}>{r.bucket_name}</option>
                  ))}
                </select>
                <select
                  value={course.status}
                  onChange={(e) => updateCourse(i, 'status', e.target.value)}
                  className="w-32 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="completed">Completed</option>
                  <option value="in_progress">In Progress</option>
                  <option value="planned">Planned</option>
                  <option value="not_scheduled">Not Scheduled</option>
                </select>
                <input
                  value={course.grade || ''}
                  onChange={(e) => updateCourse(i, 'grade', e.target.value)}
                  className="w-16 bg-dark-800 border border-dark-600 text-white rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                  placeholder="Grade"
                />
                <button onClick={() => removeCourse(i)} className="text-dark-400 hover:text-red-400 transition-colors">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button onClick={() => onConfirm({ requirements, courses })}>
          Confirm & Save
        </Button>
      </div>
    </div>
  );
}
