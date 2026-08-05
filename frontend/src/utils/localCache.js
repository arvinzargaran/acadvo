/**
 * localStorage keys that hold user-specific data, and the routine that clears
 * them on logout.
 *
 * localStorage is per-origin, not per-session: nothing removes these when a
 * user signs out, so on a shared machine (a library or lab computer — very much
 * this app's audience) the next person to open the app sees the previous user's
 * AI weekly summary, DSA progress and goals. The auth cookie is gone, but the
 * cached copy of their academic data is still sitting in the browser.
 *
 * `theme` is deliberately NOT listed: it is a device preference with no personal
 * content, and clearing it would make the UI flash to light mode on every logout.
 */
export const USER_DATA_KEYS = [
  'acadvo_weekly_summary', // AI-generated summary of the user's academic standing
  'acadvo_dsa', // DSA problem completion state
  'dsa_weekly_goal', // weekly DSA target
  'acadvo_tour_complete', // per-user onboarding state; a new user should see the tour
];

export function clearCachedUserData() {
  for (const key of USER_DATA_KEYS) {
    try {
      localStorage.removeItem(key);
    } catch {
      // Safari private mode and similar can throw on storage access. Failing to
      // clear a cache must never block the user from signing out.
    }
  }
}
