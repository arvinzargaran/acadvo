import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { resetPassword } from '../api/auth';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import AuthLayout from '../components/layout/AuthLayout';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await resetPassword(token, password);
      setDone(true);
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : 'Could not reset password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout eyebrow="Account recovery" title="New password">
      {!token ? (
        <div className="space-y-4">
          <p className="text-red-600 dark:text-red-400 text-sm">This reset link is missing its token. Request a new one.</p>
          <Link to="/forgot-password" className="inline-block text-primary-600 dark:text-primary-400 hover:underline text-sm font-medium">
            Request a reset link
          </Link>
        </div>
      ) : done ? (
        <p className="text-green-600 dark:text-green-400">Password updated! Redirecting to sign in…</p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-sm text-red-600 dark:text-red-400">
              {error}
            </div>
          )}
          <Input
            label="New Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Min 8 characters"
            minLength={8}
            required
          />
          <Input
            label="Confirm New Password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Repeat your password"
            required
          />
          <Button type="submit" variant="accent" loading={loading} className="w-full">
            Reset password
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
