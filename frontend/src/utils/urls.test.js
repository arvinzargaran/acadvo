import { describe, expect, it } from 'vitest';

import { safeExternalUrl } from './urls';

describe('safeExternalUrl', () => {
  it('passes through ordinary http(s) links', () => {
    expect(safeExternalUrl('https://github.com/user/repo')).toBe(
      'https://github.com/user/repo'
    );
    expect(safeExternalUrl('http://example.com/a?b=c')).toBe('http://example.com/a?b=c');
    expect(safeExternalUrl('  https://example.com  ')).toBe('https://example.com/');
  });

  it('rejects script-capable schemes', () => {
    // React renders these hrefs, so anything that survives here executes on
    // our own origin when the link is clicked.
    expect(safeExternalUrl('javascript:alert(1)')).toBeUndefined();
    expect(safeExternalUrl('JavaScript:alert(1)')).toBeUndefined();
    expect(safeExternalUrl('  javascript:alert(1)')).toBeUndefined();
    expect(safeExternalUrl('data:text/html,<script>alert(1)</script>')).toBeUndefined();
    expect(safeExternalUrl('vbscript:msgbox(1)')).toBeUndefined();
    expect(safeExternalUrl('blob:https://example.com/uuid')).toBeUndefined();
    expect(safeExternalUrl('file:///etc/passwd')).toBeUndefined();
  });

  it('rejects relative and malformed values', () => {
    expect(safeExternalUrl('/admin')).toBeUndefined();
    expect(safeExternalUrl('//evil.com')).toBeUndefined();
    expect(safeExternalUrl('not a url')).toBeUndefined();
  });

  it('rejects non-strings and blanks', () => {
    expect(safeExternalUrl('')).toBeUndefined();
    expect(safeExternalUrl('   ')).toBeUndefined();
    expect(safeExternalUrl(null)).toBeUndefined();
    expect(safeExternalUrl(undefined)).toBeUndefined();
    expect(safeExternalUrl(42)).toBeUndefined();
    expect(safeExternalUrl({})).toBeUndefined();
  });
});
