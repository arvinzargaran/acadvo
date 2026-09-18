import { afterEach, describe, expect, it, vi } from 'vitest';

import { privacyEmail } from './config';

/**
 * The privacy policy prints this address as the place to send access requests
 * and complaints. PIPEDA Principle 8 makes it a factual claim, so a derivation
 * that quietly produces `privacy@co.uk` is not a cosmetic bug — it is a policy
 * naming a mailbox nobody controls.
 */
describe('privacyEmail', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('uses the configured override verbatim, whatever the host is', () => {
    vi.stubEnv('VITE_PRIVACY_EMAIL', '  legal@acadvo.example  ');
    expect(privacyEmail('app.acadvo.ca')).toBe('legal@acadvo.example');
  });

  it('falls back to derivation when the override is blank', () => {
    vi.stubEnv('VITE_PRIVACY_EMAIL', '   ');
    expect(privacyEmail('acadvo.ca')).toBe('privacy@acadvo.ca');
  });

  it('keeps a bare registrable domain intact', () => {
    expect(privacyEmail('acadvo.ca')).toBe('privacy@acadvo.ca');
    expect(privacyEmail('acadvo.com')).toBe('privacy@acadvo.com');
  });

  it('strips the app subdomain so the alias sits on the registrable domain', () => {
    expect(privacyEmail('app.acadvo.ca')).toBe('privacy@acadvo.ca');
    expect(privacyEmail('www.acadvo.ca')).toBe('privacy@acadvo.ca');
    expect(privacyEmail('staging.app.acadvo.ca')).toBe('privacy@acadvo.ca');
  });

  it('does not collapse a two-part public suffix to the suffix itself', () => {
    expect(privacyEmail('acadvo.co.uk')).toBe('privacy@acadvo.co.uk');
    expect(privacyEmail('app.acadvo.co.uk')).toBe('privacy@acadvo.co.uk');
    expect(privacyEmail('acadvo.com.au')).toBe('privacy@acadvo.com.au');
  });

  it('treats a public-suffix word as a normal label when it is not in suffix position', () => {
    // The heuristic looks only at the second-to-last label, so a site actually
    // named `co.acadvo.ca` is not mistaken for a ccTLD registration.
    expect(privacyEmail('co.acadvo.ca')).toBe('privacy@acadvo.ca');
  });

  it('leaves IP literals whole — there is no domain to strip back to', () => {
    expect(privacyEmail('192.168.1.10')).toBe('privacy@192.168.1.10');
    expect(privacyEmail('[::1]')).toBe('privacy@[::1]');
  });

  it('handles single-label and fully-qualified hosts', () => {
    expect(privacyEmail('localhost')).toBe('privacy@localhost');
    // A root dot is DNS syntax, not part of a mail domain.
    expect(privacyEmail('acadvo.ca.')).toBe('privacy@acadvo.ca');
    expect(privacyEmail('app.acadvo.ca.')).toBe('privacy@acadvo.ca');
  });

  it('normalises case, because mail domains are case-insensitive but ugly', () => {
    expect(privacyEmail('APP.Acadvo.CA')).toBe('privacy@acadvo.ca');
  });

  it('never returns a bare `privacy@` when the host is unknown', () => {
    expect(privacyEmail('')).toBe('privacy@localhost');
  });
});

describe('privacyEmail on hosting platforms', () => {
  // The failure these pin is silent and points at a real company: on a preview
  // deployment the policy would name the *platform's* mailbox as the PIPEDA
  // contact, and a student's access request would go to a stranger.
  it.each([
    ['acadvo.vercel.app', 'privacy@acadvo.vercel.app'],
    ['acadvo.onrender.com', 'privacy@acadvo.onrender.com'],
    ['acadvo.netlify.app', 'privacy@acadvo.netlify.app'],
    ['acadvo.pages.dev', 'privacy@acadvo.pages.dev'],
    ['acadvo.github.io', 'privacy@acadvo.github.io'],
  ])('keeps the site label on %s', (host, expected) => {
    expect(privacyEmail(host)).toBe(expected);
  });

  it('still collapses a subdomain on an ordinary domain', () => {
    expect(privacyEmail('app.acadvo.ca')).toBe('privacy@acadvo.ca');
  });
});
