import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { verifyEmail } from '../api/auth';

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [status, setStatus] = useState(token ? 'verifying' : 'notoken');
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true; // guard against React 18 StrictMode double-invoke
    verifyEmail(token)
      .then(() => setStatus('success'))
      .catch(() => setStatus('error'));
  }, [token]);

  const messages = {
    verifying: { title: 'Verifying your email…', body: 'One moment.', color: 'text-gray-300' },
    success: { title: 'Email verified', body: 'Your email address is confirmed.', color: 'text-green-400' },
    error: { title: 'Verification failed', body: 'This link is invalid or has expired. You can request a new one from Settings.', color: 'text-red-400' },
    notoken: { title: 'Missing token', body: 'This verification link is incomplete.', color: 'text-red-400' },
  };
  const m = messages[status];

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-dark-950">
      <div className="w-full max-w-sm text-center">
        <h1 className="text-3xl font-bold font-display text-primary-600 mb-8">Acadvo</h1>
        <div className="bg-white/5 border border-white/10 rounded-xl p-8 shadow-sm space-y-3">
          <h2 className={`text-lg font-semibold ${m.color}`}>{m.title}</h2>
          <p className="text-gray-400 text-sm">{m.body}</p>
          <Link to="/dashboard" className="inline-block mt-2 text-primary-600 hover:text-primary-500 hover:underline text-sm font-medium">
            Go to dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
