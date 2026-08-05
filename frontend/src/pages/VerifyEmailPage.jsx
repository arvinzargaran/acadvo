import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { verifyEmail } from '../api/auth';
import Card from '../components/ui/Card';
import { useAuth } from '../context/AuthContext';

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const { refreshUser } = useAuth();
  const token = searchParams.get('token') || '';
  const [status, setStatus] = useState(token ? 'verifying' : 'notoken');
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true; // guard against StrictMode's double-invoke
    verifyEmail(token)
      .then(async () => {
        setStatus('success');
        // Re-fetch the user so `email_verified` is current — otherwise the
        // "verify your email" banner keeps showing after a successful
        // verification, because the context still holds the stale record.
        // Harmless when nobody is signed in; refreshUser swallows the 401.
        await refreshUser();
      })
      .catch(() => setStatus('error'));
  }, [token, refreshUser]);

  const messages = {
    verifying: { title: 'Verifying your email…', body: 'One moment.', color: 'text-dark-200', eyebrow: 'Please wait' },
    success: { title: 'Email verified', body: 'Your email address is confirmed.', color: 'text-green-600 dark:text-green-400', eyebrow: 'All set' },
    error: { title: 'Verification failed', body: 'This link is invalid or has expired. You can request a new one from Settings.', color: 'text-red-600 dark:text-red-400', eyebrow: 'Something went wrong' },
    notoken: { title: 'Missing token', body: 'This verification link is incomplete.', color: 'text-red-600 dark:text-red-400', eyebrow: 'Something went wrong' },
  };
  const m = messages[status];

  return (
    <div className="relative min-h-screen flex items-center justify-center px-4 bg-dark-950 overflow-hidden">
      <div className="aurora-warm absolute inset-0 pointer-events-none" />
      <div className="relative w-full max-w-sm text-center">
        <Link to="/" className="inline-block text-2xl font-bold font-display text-primary-600 hover:opacity-80 transition-opacity mb-8">Acadvo</Link>
        <Card className="space-y-3">
          <p className="eyebrow">{m.eyebrow}</p>
          <h2 className={`font-display text-2xl tracking-tight ${m.color}`}>{m.title}</h2>
          <p className="text-dark-400 text-sm">{m.body}</p>
          <Link to="/dashboard" className="inline-block mt-2 text-primary-600 dark:text-primary-400 hover:underline text-sm font-medium">
            Go to dashboard
          </Link>
        </Card>
      </div>
    </div>
  );
}
