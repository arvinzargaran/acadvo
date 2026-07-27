import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import client from '../api/client';
import { deleteAccount, changePassword, getCalendarFeed, regenerateCalendarFeed } from '../api/users';
import { resendVerification } from '../api/auth';
import { getErrorMessage } from '../utils/errors';

export default function SettingsPage() {
  const { user, setUser, logout } = useAuth();
  const [form, setForm] = useState({
    full_name: user?.full_name || '',
    university: user?.university || '',
    program: user?.program || '',
    start_year: user?.start_year || '',
    expected_graduation_year: user?.expected_graduation_year || '',
    country: user?.country || '',
    city: user?.city || '',
    career_target: user?.career_target || '',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [showDelete, setShowDelete] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');

  const [resendState, setResendState] = useState('idle'); // idle | sending | sent | error

  const [feedUrl, setFeedUrl] = useState('');
  const [feedLoading, setFeedLoading] = useState(false);
  const [feedError, setFeedError] = useState('');
  const [feedCopied, setFeedCopied] = useState(false);
  const [showRegenerateConfirm, setShowRegenerateConfirm] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  const handleShowFeed = async () => {
    setFeedLoading(true);
    setFeedError('');
    try {
      const { data } = await getCalendarFeed();
      setFeedUrl(data.feed_url);
    } catch (err) {
      setFeedError(getErrorMessage(err, 'Failed to load your calendar link.'));
    } finally {
      setFeedLoading(false);
    }
  };

  const handleCopyFeed = async () => {
    await navigator.clipboard.writeText(feedUrl);
    setFeedCopied(true);
    setTimeout(() => setFeedCopied(false), 2000);
  };

  const handleRegenerateFeed = async () => {
    setRegenerating(true);
    setFeedError('');
    try {
      const { data } = await regenerateCalendarFeed();
      setFeedUrl(data.feed_url);
      setShowRegenerateConfirm(false);
    } catch (err) {
      setFeedError(getErrorMessage(err, 'Failed to reset your calendar link.'));
    } finally {
      setRegenerating(false);
    }
  };

  const handleResendVerification = async () => {
    setResendState('sending');
    try {
      await resendVerification();
      setResendState('sent');
    } catch {
      setResendState('error');
    }
  };

  const [pwForm, setPwForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwError, setPwError] = useState('');
  const [pwSaved, setPwSaved] = useState(false);

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setPwError('');
    if (pwForm.new_password !== pwForm.confirm_password) {
      setPwError('New passwords do not match.');
      return;
    }
    setPwSaving(true);
    try {
      await changePassword(pwForm.current_password, pwForm.new_password);
      setPwForm({ current_password: '', new_password: '', confirm_password: '' });
      setPwSaved(true);
      setTimeout(() => setPwSaved(false), 2000);
    } catch (err) {
      setPwError(getErrorMessage(err, 'Failed to change password.'));
    } finally {
      setPwSaving(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveError('');
    try {
      const data = { ...form };
      if (data.start_year) data.start_year = parseInt(data.start_year);
      if (data.expected_graduation_year) data.expected_graduation_year = parseInt(data.expected_graduation_year);
      const res = await client.put('/users/me', data);
      setUser(res.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setSaveError(getErrorMessage(err, 'Failed to save changes.'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deletePassword) {
      setDeleteError('Enter your password to confirm.');
      return;
    }
    setDeleting(true);
    setDeleteError('');
    try {
      await deleteAccount(deletePassword);
      logout();
    } catch (err) {
      setDeleteError(getErrorMessage(err, 'Failed to delete account.'));
      setDeleting(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      <Card>
        <h2 className="text-white font-semibold mb-4">Profile</h2>
        <form onSubmit={handleSave} className="space-y-4">
          <Input label="Full Name" value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} />
          <div className="grid grid-cols-2 gap-4">
            <Input label="University" value={form.university} onChange={e => setForm(f => ({ ...f, university: e.target.value }))} />
            <Input label="Program" value={form.program} onChange={e => setForm(f => ({ ...f, program: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input label="Start Year" type="number" value={form.start_year} onChange={e => setForm(f => ({ ...f, start_year: e.target.value }))} />
            <Input label="Expected Graduation" type="number" value={form.expected_graduation_year} onChange={e => setForm(f => ({ ...f, expected_graduation_year: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input label="Country" value={form.country} onChange={e => setForm(f => ({ ...f, country: e.target.value }))} />
            <Input label="City" value={form.city} onChange={e => setForm(f => ({ ...f, city: e.target.value }))} />
          </div>
          <div>
            <label className="block text-sm text-dark-300 mb-1">Career Target</label>
            <textarea
              value={form.career_target}
              onChange={e => setForm(f => ({ ...f, career_target: e.target.value }))}
              className="w-full bg-dark-800 border border-dark-600 text-white rounded-lg px-3 py-2 h-20 resize-none"
              placeholder="e.g. SWE internship → Technical Product Manager"
            />
          </div>
          {saveError && <p className="text-red-400 text-sm">{saveError}</p>}
          <div className="flex items-center gap-3">
            <Button variant="primary" type="submit" loading={saving}>Save changes</Button>
            {saved && <span className="text-green-400 text-sm">Saved!</span>}
          </div>
        </form>
      </Card>

      <Card>
        <h2 className="text-white font-semibold mb-4">Change Password</h2>
        <form onSubmit={handlePasswordChange} className="space-y-4">
          <Input label="Current Password" type="password" value={pwForm.current_password} onChange={e => setPwForm(f => ({ ...f, current_password: e.target.value }))} required />
          <Input label="New Password" type="password" value={pwForm.new_password} onChange={e => setPwForm(f => ({ ...f, new_password: e.target.value }))} required minLength={8} placeholder="Min 8 characters" />
          <Input label="Confirm New Password" type="password" value={pwForm.confirm_password} onChange={e => setPwForm(f => ({ ...f, confirm_password: e.target.value }))} required />
          {pwError && <p className="text-red-400 text-sm">{pwError}</p>}
          <div className="flex items-center gap-3">
            <Button variant="primary" type="submit" loading={pwSaving}>Update password</Button>
            {pwSaved && <span className="text-green-400 text-sm">Password updated!</span>}
          </div>
        </form>
      </Card>

      <Card>
        <h2 className="text-white font-semibold mb-2">Calendar Sync</h2>
        <p className="text-dark-300 text-sm mb-4">
          Subscribe to a live feed of your deadlines, milestones, and assessments from Google Calendar,
          Apple Calendar, or Outlook. The calendar app checks this link periodically and stays in sync automatically.
        </p>

        {!feedUrl ? (
          <Button variant="secondary" loading={feedLoading} onClick={handleShowFeed}>
            Get my calendar link
          </Button>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={feedUrl}
                onFocus={e => e.target.select()}
                className="flex-1 bg-dark-800 border border-dark-600 text-white text-sm rounded-lg px-3 py-2 truncate"
              />
              <Button variant="secondary" onClick={handleCopyFeed}>{feedCopied ? 'Copied!' : 'Copy'}</Button>
            </div>
            <p className="text-dark-400 text-xs">
              In Google Calendar: Other calendars → From URL. In Apple Calendar: File → New Calendar Subscription.
            </p>

            {!showRegenerateConfirm ? (
              <button
                onClick={() => setShowRegenerateConfirm(true)}
                className="text-dark-400 hover:text-red-400 text-xs transition"
              >
                Reset link
              </button>
            ) : (
              <div className="space-y-2">
                <p className="text-dark-300 text-xs">
                  This invalidates the current link — any calendar already subscribed will stop updating. Continue?
                </p>
                <div className="flex gap-3">
                  <Button variant="danger" loading={regenerating} onClick={handleRegenerateFeed}>Reset link</Button>
                  <Button variant="secondary" onClick={() => setShowRegenerateConfirm(false)}>Cancel</Button>
                </div>
              </div>
            )}
          </div>
        )}
        {feedError && <p className="text-red-400 text-sm mt-2">{feedError}</p>}
      </Card>

      <Card>
        <h2 className="text-white font-semibold mb-2">Email Verification</h2>
        {user?.email_verified ? (
          <p className="text-green-400 text-sm flex items-center gap-2">
            <span>✓</span> Your email address is verified.
          </p>
        ) : (
          <div className="space-y-3">
            <p className="text-dark-300 text-sm">
              Your email <span className="text-white">{user?.email}</span> isn't verified yet. Check
              your inbox for the verification link, or resend it.
            </p>
            <div className="flex items-center gap-3">
              <Button variant="secondary" loading={resendState === 'sending'} onClick={handleResendVerification}>
                Resend verification email
              </Button>
              {resendState === 'sent' && <span className="text-green-400 text-sm">Sent — check your inbox.</span>}
              {resendState === 'error' && <span className="text-red-400 text-sm">Couldn't send. Try again shortly.</span>}
            </div>
          </div>
        )}
      </Card>

      <Card className="border-red-500/30">
        <h2 className="text-red-400 font-semibold mb-2">Danger Zone</h2>
        {!showDelete ? (
          <Button variant="danger" onClick={() => setShowDelete(true)}>Delete my account</Button>
        ) : (
          <div className="space-y-3">
            <p className="text-dark-300 text-sm">This will permanently delete your account and all data. This cannot be undone.</p>
            <Input
              label="Confirm your password"
              type="password"
              value={deletePassword}
              onChange={e => setDeletePassword(e.target.value)}
              placeholder="Enter your password"
            />
            {deleteError && <p className="text-red-400 text-sm">{deleteError}</p>}
            <div className="flex gap-3">
              <Button variant="danger" loading={deleting} onClick={handleDelete}>Confirm delete</Button>
              <Button variant="secondary" onClick={() => { setShowDelete(false); setDeleteError(''); setDeletePassword(''); }}>Cancel</Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
