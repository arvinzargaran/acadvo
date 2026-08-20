import { useState } from 'react';
import toast from 'react-hot-toast';

import { resendVerification } from '../../api/auth';
import { useAuth } from '../../context/AuthContext';

/**
 * Inline notice for the places that need a verified email to work at all.
 *
 * `VerifyEmailBanner` covers the signed-in app, but it lives in the app layout —
 * and onboarding is a standalone full-screen page that never renders that
 * layout. So the one screen where the block actually stops a new user cold, the
 * degree-checklist upload at step 7, was the one screen that said nothing about
 * it until after they had chosen a file and waited for a rejected request.
 *
 * This states the rule before the user does the work, names the feature that is
 * actually blocked, and carries the resend action in place — onboarding has no
 * navigation, so "request a new link from Settings" is a dead end here.
 */
export default function VerifyEmailNotice({ feature = 'this' }) {
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
      className="mb-4 border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-900 dark:text-amber-200"
    >
      <p className="font-semibold">Verify your email to use {feature}.</p>
      <p className="mt-1 opacity-90">
        We sent a link to {user.email}. Reading it takes a click — until then this
        step is unavailable, and you can skip it and add everything by hand later.
      </p>
      <button
        type="button"
        onClick={handleResend}
        disabled={sending || sent}
        className="wf-signage mt-3 border border-amber-500/50 px-3 py-1.5 text-[10px] transition-colors hover:bg-amber-500/20 disabled:opacity-60"
      >
        {sending ? 'Sending…' : sent ? 'Link sent' : 'Resend link'}
      </button>
    </div>
  );
}
