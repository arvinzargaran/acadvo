import { useState } from 'react';
import { Link } from 'react-router';
import { forgotPassword } from '../api/auth';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import AuthLayout from '../components/layout/AuthLayout';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout eyebrow="Account recovery" title="Reset password">
      {sent ? (
        <div className="space-y-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-green-500/15 ring-1 ring-inset ring-green-500/30">
            <svg className="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          </div>
          <p className="text-dark-200">
            If an account exists for <span className="font-medium text-dark-50">{email}</span>, we've sent a
            link to reset your password. Check your inbox.
          </p>
          <Link to="/login" className="inline-block text-primary-600 dark:text-primary-400 hover:underline text-sm font-medium">
            Back to sign in
          </Link>
        </div>
      ) : (
        <>
          <p className="text-dark-400 text-sm mb-6">
            Enter your email and we'll send you a link to reset your password.
          </p>
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-sm text-red-600 dark:text-red-400">
                {error}
              </div>
            )}
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
            <Button type="submit" variant="accent" loading={loading} className="w-full">
              Send reset link
            </Button>
          </form>
          <p className="mt-4 text-sm text-dark-400">
            <Link to="/login" className="text-primary-600 dark:text-primary-400 hover:underline font-medium">
              Back to sign in
            </Link>
          </p>
        </>
      )}
    </AuthLayout>
  );
}
