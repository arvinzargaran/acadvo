import { useState } from 'react';
import toast from 'react-hot-toast';

import { resendVerification } from '../../api/auth';
import { useAuth } from '../../context/AuthContext';

/**
 * Shown app-wide while the signed-in account's email is unverified.
 *
 * The API refuses the AI features for unverified accounts (see
 * require_verified_email in backend/app/deps.py) — every model call costs money,
 * and a per-IP rate limit does not stop someone cycling throwaway addresses.
 * Ordinary editing still works, so without this banner the app looks entirely
 * normal until the advisor silently refuses. This states the rule up front and
 * gives the user the one action that fixes it.
 */
export default function VerifyEmailBanner() {
  const { user } = useAuth();
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  if (!user || user.email_verified) return null;

  const handleResend = async () => {
    setSending(true);
    try {
      await resendVerification();
      setSent(true);
      toast.success(`Verification link sent to ${user.email}`);
    } catch {
      toast.error('Could not send the verification email. Please try again shortly.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-amber-300/60 bg-amber-50 px-5 py-3 text-sm text-amber-900 sm:px-8 lg:px-12 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200"
    >
      <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      </svg>
      <span className="flex-1 min-w-[16rem]">
        <strong className="font-semibold">Verify your email to unlock the AI advisor.</strong>{' '}
        We sent a link to {user.email}. Everything else works in the meantime.
      </span>
      <button
        type="button"
        onClick={handleResend}
        disabled={sending || sent}
        className="shrink-0 rounded-lg border border-amber-400/70 px-3 py-1.5 font-medium transition-colors hover:bg-amber-100 disabled:opacity-60 dark:hover:bg-amber-500/20"
      >
        {sending ? 'Sending…' : sent ? 'Link sent' : 'Resend link'}
      </button>
    </div>
  );
}
