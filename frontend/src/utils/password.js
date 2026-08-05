/**
 * Client-side mirror of the server's password policy.
 *
 * This is UX, not enforcement — the real check is in backend/app/schemas/password.py
 * and runs regardless of what the browser does. The point is that a user should
 * learn the rule while typing, rather than filling in a whole form and getting
 * a 422 back. Keep the two in sync when either changes.
 */
export const MIN_PASSWORD_LENGTH = 12;

export const PASSWORD_HINT = `At least ${MIN_PASSWORD_LENGTH} characters`;

export const PASSWORD_HELP =
  `Use at least ${MIN_PASSWORD_LENGTH} characters. A short phrase you can remember ` +
  `("two rusty blue bicycles") is both stronger and easier than a short scramble.`;
