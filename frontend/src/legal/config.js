/**
 * The facts the legal pages assert about who runs this service.
 *
 * They live in one file because they appear in both documents and in the
 * account-deletion copy, and a privacy policy that names a different operator
 * than the terms is worse than one that names neither. Everything here is a
 * factual claim someone can hold you to — change it when the fact changes, not
 * to make a page read better.
 */

/** Where personal data is stored at rest. Update this if the host moves. */
export const HOSTING_REGION = 'Canada';

/** Legal operator of the service — a named individual, not a company. */
export const OPERATOR = 'the individual who operates acadvo';

/** Province whose law governs the terms, and whose courts hear disputes. */
export const GOVERNING_PROVINCE = 'Ontario';

/** Minimum age for an account. Enforced as a declaration at registration. */
export const MINIMUM_AGE = 18;

/**
 * Second-level labels that are public suffixes rather than anybody's domain.
 *
 * A deliberate stand-in for the real Public Suffix List, which is thousands of
 * entries, changes without notice, and would have to be shipped to every
 * visitor to decide one mailto. This covers the suffix shapes a Canadian
 * student tool plausibly deploys under; a deployment on anything more exotic
 * (`acadvo.com.br` is handled, `acadvo.pvt.k12.ma.us` is not) must set
 * VITE_PRIVACY_EMAIL, which overrides all of this.
 */
const PUBLIC_SECOND_LEVEL = new Set(['co', 'com', 'net', 'org', 'gov', 'edu', 'ac', 'gc']);

/**
 * Hosting platforms whose whole two-label domain is a public suffix.
 *
 * These are the ones that bite, because the failure is silent and points at a
 * real company: on `acadvo.vercel.app` the rule above sees an ordinary
 * second-level label (`vercel`) and collapses the address to
 * `privacy@vercel.app` — so the privacy policy names Vercel's mailbox as the
 * PIPEDA contact, and a student's access request goes to a stranger. A preview
 * or staging deployment on any of these is the normal way that happens.
 */
const PLATFORM_SUFFIXES = new Set([
  'vercel.app',
  'netlify.app',
  'onrender.com',
  'railway.app',
  'fly.dev',
  'pages.dev',
  'workers.dev',
  'github.io',
  'herokuapp.com',
  'web.app',
  'firebaseapp.com',
]);

/**
 * Address for privacy requests and complaints (PIPEDA Principle 8 requires a
 * reachable contact for the person accountable for the data).
 *
 * Defaults to `privacy@` on the domain the app is actually served from, so a
 * deployment cannot ship a policy pointing at somebody else's mailbox. Override
 * with VITE_PRIVACY_EMAIL when the alias lives on a different domain — and make
 * sure the mailbox exists: a policy naming an address that bounces fails the
 * openness requirement more completely than a missing page.
 *
 * `hostname` is injectable only so the derivation can be tested: window.location
 * is unforgeable in jsdom and cannot be stubbed.
 */
export function privacyEmail(hostname) {
  const configured = import.meta.env.VITE_PRIVACY_EMAIL;
  if (configured && configured.trim()) return configured.trim();

  const fromWindow = typeof window !== 'undefined' ? window.location.hostname : '';
  // A fully-qualified name may carry a root dot (`acadvo.ca.`); it is part of
  // DNS, not of a mail domain, so it would make the address unroutable.
  const host = (hostname ?? fromWindow).trim().toLowerCase().replace(/\.+$/, '');
  if (!host) return 'privacy@localhost';

  // An IP literal has no registrable domain to strip back to — dropping a label
  // would name a different host entirely.
  if (host.startsWith('[') || /^\d{1,3}(\.\d{1,3}){3}$/.test(host)) return `privacy@${host}`;

  const parts = host.split('.').filter(Boolean);
  if (parts.length < 3) return `privacy@${parts.join('.')}`;

  // app.acadvo.ca -> acadvo.ca, so the alias sits on the registrable domain
  // rather than on the web app's subdomain. Keeping three labels when the
  // second-to-last is itself a public suffix stops acadvo.co.uk collapsing to
  // the meaningless privacy@co.uk.
  const lastTwo = parts.slice(-2).join('.');
  const keep =
    PUBLIC_SECOND_LEVEL.has(parts[parts.length - 2]) || PLATFORM_SUFFIXES.has(lastTwo) ? 3 : 2;
  return `privacy@${parts.slice(-keep).join('.')}`;
}

/**
 * The version stamped against an account when it accepts the terms.
 *
 * Sent at registration and stored server-side, so "which version did this
 * person agree to" stays answerable after the documents change. Bump it
 * together with LAST_UPDATED, and with TERMS_VERSION in
 * backend/app/services/auth.py, whenever the terms change materially.
 */
export const TERMS_VERSION = '2026-08-23';

/** Last substantive revision. Bump when you change what either document says. */
export const LAST_UPDATED = '23 August 2026';
