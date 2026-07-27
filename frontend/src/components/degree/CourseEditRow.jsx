import { useState, useMemo } from 'react';
import { useAuth } from '../../context/AuthContext';
import { getScale } from '../../data/gradingScales';

export default function CourseEditRow({ course, requirements, credentials = [], onSave, onCancel }) {
  const { user } = useAuth();
  const { scale } = useMemo(() => getScale(user?.university), [user?.university]);
  const gradeOptions = scale.grades;

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

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const inputClass = 'bg-dark-800 border border-dark-600 rounded-md px-2.5 py-1.5 text-white text-sm w-full min-w-0 focus:outline-none focus:border-primary-500';

  return (
    <tr className="border-b border-dark-700/50 bg-dark-700/30 align-top">
      <td className="px-3 py-2.5">
        <input
          value={form.course_code}
          onChange={e => handleChange('course_code', e.target.value)}
          className={`${inputClass} min-w-[6rem]`}
        />
      </td>
      <td className="px-3 py-2.5">
        <input
          value={form.course_name}
          onChange={e => handleChange('course_name', e.target.value)}
          className={`${inputClass} min-w-[10rem]`}
        />
      </td>
      <td className="px-3 py-2.5">
        <input
          type="number"
          step="0.25"
          value={form.credit_value}
          onChange={e => handleChange('credit_value', parseFloat(e.target.value))}
          className={`${inputClass} w-20`}
        />
      </td>
      <td className="px-3 py-2.5">
        <input
          value={form.term}
          onChange={e => handleChange('term', e.target.value)}
          className={`${inputClass} min-w-[7rem]`}
          placeholder="e.g. Fall 2026"
        />
      </td>
      <td className="px-3 py-2.5">
        <select
          value={form.status}
          onChange={e => handleChange('status', e.target.value)}
          className={inputClass}
        >
          <option value="completed">Completed</option>
          <option value="in_progress">In Progress</option>
          <option value="planned">Planned</option>
          <option value="not_scheduled">Not Scheduled</option>
        </select>
      </td>
      <td className="px-3 py-2.5">
        <select
          value={form.grade}
          onChange={e => handleChange('grade', e.target.value)}
          className={`${inputClass} w-24`}
        >
          <option value="">-- No grade --</option>
          {gradeOptions.map(g => (
            <option key={g.letter} value={g.letter}>{g.letter}</option>
          ))}
          <option value="Pass">Pass</option>
          <option value="Fail">Fail</option>
        </select>
      </td>
      <td className="px-3 py-2.5">
        <select
          value={form.requirement_bucket_id}
          onChange={e => handleChange('requirement_bucket_id', e.target.value || null)}
          className={`${inputClass} min-w-[8rem]`}
        >
          <option value="">None</option>
          {requirements.map(r => (
            <option key={r.id} value={r.id}>{r.bucket_name}</option>
          ))}
        </select>
      </td>
      <td className="px-3 py-2.5">
        <select
          value={form.credential_id}
          onChange={e => handleChange('credential_id', e.target.value || null)}
          className={`${inputClass} min-w-[8rem]`}
        >
          <option value="">None</option>
          {credentials.map(c => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </td>
      <td className="px-3 py-2.5 text-right whitespace-nowrap">
        <button
          onClick={() => onSave({
            ...form,
            requirement_bucket_id: form.requirement_bucket_id || null,
            credential_id: form.credential_id || null,
          })}
          className="text-green-400 hover:text-green-300 text-sm mr-2"
        >
          Save
        </button>
        <button onClick={onCancel} className="text-dark-400 hover:text-dark-300 text-sm">
          Cancel
        </button>
      </td>
    </tr>
  );
}
