import { useState } from 'react';
import Input from '../ui/Input';
import Button from '../ui/Button';

// Form for creating a requirement bucket (POST /degree/requirements).
export default function RequirementForm({ onSave, onCancel }) {
  const [form, setForm] = useState({
    bucket_name: '',
    credits_required: 3,
    description: '',
    notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.bucket_name.trim()) {
      setError('Please enter a name for this requirement.');
      return;
    }
    setError('');
    setSaving(true);
    try {
      await onSave({
        bucket_name: form.bucket_name.trim(),
        credits_required: parseFloat(form.credits_required) || 0,
        description: form.description.trim() || null,
        notes: form.notes.trim() || null,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Requirement name"
          value={form.bucket_name}
          onChange={e => handleChange('bucket_name', e.target.value)}
          placeholder="e.g. Core Requirements"
          error={error}
        />
        <Input
          label="Credits required"
          type="number"
          step="0.5"
          min="0"
          value={form.credits_required}
          onChange={e => handleChange('credits_required', e.target.value)}
        />
      </div>

      <Input
        label="Description (optional)"
        value={form.description}
        onChange={e => handleChange('description', e.target.value)}
        placeholder="Short summary of this requirement"
      />

      <div className="space-y-1">
        <label className="block text-sm font-medium text-gray-700 dark:text-dark-300">Notes (optional)</label>
        <textarea
          value={form.notes}
          onChange={e => handleChange('notes', e.target.value)}
          rows={3}
          placeholder="Any additional details"
          className="w-full bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm placeholder-gray-400 dark:placeholder-dark-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
        />
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="accent" loading={saving}>Add requirement</Button>
      </div>
    </form>
  );
}
