import { useState, useMemo } from 'react';
import { useAuth } from '../../context/AuthContext';
import { getScale } from '../../data/gradingScales';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Button from '../ui/Button';

const statusOptions = [
  { value: 'completed', label: 'Completed' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'planned', label: 'Planned' },
  { value: 'not_scheduled', label: 'Not Scheduled' },
];

// Stacked course form used inside a Modal for add/edit on small screens
// (and anywhere a roomy form is preferable to the cramped inline row).
export default function CourseForm({ course, requirements, credentials = [], onSave, onCancel, submitLabel = 'Save' }) {
  const { user } = useAuth();
  const { scale } = useMemo(() => getScale(user?.university), [user?.university]);

  const gradeOptions = [
    ...scale.grades.map(g => ({ value: g.letter, label: g.letter })),
    { value: 'Pass', label: 'Pass' },
    { value: 'Fail', label: 'Fail' },
  ];

  const [form, setForm] = useState({
    course_code: course.course_code,
    course_name: course.course_name,
    credit_value: course.credit_value,
    status: course.status,
    grade: course.grade || '',
    term: course.term || '',
    requirement_bucket_id: course.requirement_bucket_id || '',
    credential_id: course.credential_id || '',
  });
  const [saving, setSaving] = useState(false);

  const handleChange = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave({
        ...form,
        requirement_bucket_id: form.requirement_bucket_id || null,
        credential_id: form.credential_id || null,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Course code"
          value={form.course_code}
          onChange={e => handleChange('course_code', e.target.value)}
          placeholder="e.g. CS101"
        />
        <Input
          label="Credits"
          type="number"
          step="0.25"
          value={form.credit_value}
          onChange={e => handleChange('credit_value', parseFloat(e.target.value))}
        />
      </div>

      <Input
        label="Course name"
        value={form.course_name}
        onChange={e => handleChange('course_name', e.target.value)}
        placeholder="e.g. Intro to Computer Science"
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Semester / term"
          value={form.term}
          onChange={e => handleChange('term', e.target.value)}
          placeholder="e.g. Fall 2026"
        />
        <Select
          label="Status"
          value={form.status}
          onChange={e => handleChange('status', e.target.value)}
          options={statusOptions}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700 dark:text-dark-300">Grade</label>
          <select
            value={form.grade}
            onChange={e => handleChange('grade', e.target.value)}
            className="w-full bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
          >
            <option value="">-- No grade --</option>
            {gradeOptions.map(g => (
              <option key={g.value} value={g.value}>{g.label}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700 dark:text-dark-300">Requirement</label>
          <select
            value={form.requirement_bucket_id}
            onChange={e => handleChange('requirement_bucket_id', e.target.value)}
            className="w-full bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
          >
            <option value="">None</option>
            {requirements.map(r => (
              <option key={r.id} value={r.id}>{r.bucket_name}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-1">
        <label className="block text-sm font-medium text-gray-700 dark:text-dark-300">Credential</label>
        <select
          value={form.credential_id}
          onChange={e => handleChange('credential_id', e.target.value)}
          className="w-full bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
        >
          <option value="">None</option>
          {credentials.map(c => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="accent" loading={saving}>{submitLabel}</Button>
      </div>
    </form>
  );
}
