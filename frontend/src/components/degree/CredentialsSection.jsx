import { useState } from 'react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import Modal from '../ui/Modal';
import ProgressBar from '../ui/ProgressBar';
import { createCredential, updateCredential, deleteCredential } from '../../api/degree';
import { getErrorMessage } from '../../utils/errors';

const EMPTY_FORM = { name: '', description: '', total_credits_required: '' };

export default function CredentialsSection({ credentials, courses, onRefresh }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  function openAdd() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setError('');
    setModalOpen(true);
  }

  function openEdit(cred) {
    setEditing(cred);
    setForm({
      name: cred.name,
      description: cred.description || '',
      total_credits_required: cred.total_credits_required != null ? String(cred.total_credits_required) : '',
    });
    setError('');
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditing(null);
    setError('');
  }

  async function handleSave(e) {
    e.preventDefault();
    if (!form.name.trim()) { setError('Name is required'); return; }
    const credits = parseFloat(form.total_credits_required);
    if (form.total_credits_required && (isNaN(credits) || credits <= 0)) {
      setError('Credits must be a positive number');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        total_credits_required: form.total_credits_required ? credits : null,
      };
      if (editing) {
        await updateCredential(editing.id, payload);
      } else {
        await createCredential(payload);
      }
      closeModal();
      await onRefresh();
    } catch (err) {
      setError(getErrorMessage(err, 'Something went wrong.'));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    await deleteCredential(id);
    setConfirmDeleteId(null);
    await onRefresh();
  }

  function creditsCompleted(credId) {
    return courses
      .filter(c => c.credential_id === credId && c.status === 'completed')
      .reduce((sum, c) => sum + (c.credit_value || 0), 0);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-dark-400 text-sm">
          Track minors, certificates, and specializations alongside your degree.
        </p>
        <Button onClick={openAdd}>+ Add Credential</Button>
      </div>

      {credentials.length === 0 ? (
        <Card>
          <div className="text-center py-12">
            <svg className="w-12 h-12 text-dark-600 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            <p className="text-dark-400">No credentials added yet</p>
            <p className="text-dark-500 text-sm mt-1">Add a minor, certificate, or specialization to track your progress.</p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {credentials.map(cred => {
            const completed = creditsCompleted(cred.id);
            const total = cred.total_credits_required || 0;
            const pct = total > 0 ? Math.min(100, (completed / total) * 100) : 0;
            const assignedCourses = courses.filter(c => c.credential_id === cred.id);

            return (
              <Card key={cred.id}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-dark-50 font-semibold">{cred.name}</h3>
                    {cred.description && (
                      <p className="text-dark-400 text-sm mt-0.5">{cred.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => openEdit(cred)}
                      className="text-primary-400 hover:text-primary-300 text-sm px-2 py-1 transition-colors"
                    >
                      Edit
                    </button>
                    {confirmDeleteId === cred.id ? (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleDelete(cred.id)}
                          className="text-red-400 hover:text-red-300 text-xs px-2 py-1 bg-red-500/10 rounded transition-colors"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="text-dark-400 hover:text-dark-300 text-xs px-2 py-1 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDeleteId(cred.id)}
                        className="text-dark-500 hover:text-red-400 text-sm px-2 py-1 transition-colors"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>

                {total > 0 ? (
                  <ProgressBar
                    value={pct}
                    label={`${completed} / ${total} credits`}
                  />
                ) : (
                  <p className="text-dark-500 text-xs">No credit target set</p>
                )}

                {assignedCourses.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-dark-700">
                    <p className="text-dark-400 text-xs mb-1.5">{assignedCourses.length} course{assignedCourses.length !== 1 ? 's' : ''} assigned</p>
                    <div className="flex flex-wrap gap-1.5">
                      {assignedCourses.map(c => (
                        <span key={c.id} className="text-xs bg-dark-700 text-dark-300 px-2 py-0.5 rounded">
                          {c.course_code}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Add/Edit Modal */}
      <Modal isOpen={modalOpen} onClose={closeModal} title={editing ? 'Edit Credential' : 'Add Credential'}>
        <form onSubmit={handleSave} className="space-y-4">
          <Input
            label="Name"
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            placeholder="e.g. Minor in Mathematics"
            required
          />
          <Input
            label="Description (optional)"
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            placeholder="Brief description"
          />
          <Input
            label="Total Credits Required (optional)"
            type="number"
            step="0.5"
            min="0"
            value={form.total_credits_required}
            onChange={e => setForm(f => ({ ...f, total_credits_required: e.target.value }))}
            placeholder="e.g. 4.0"
          />
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button variant="secondary" type="button" onClick={closeModal}>Cancel</Button>
            <Button type="submit" loading={saving}>{editing ? 'Save Changes' : 'Add Credential'}</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
