import Badge from '../ui/Badge';

/**
 * Renders what the university's own requirement rules say about a course
 * counting toward a bucket.
 *
 * The one rule this component exists to enforce: **never show "this counts"
 * without showing where that came from.** A wrong degree-credit claim is the
 * only mistake in Acadvo that fails silently — the student believes it, plans
 * around it, and finds out at their graduation audit a year later.
 *
 * So `verdict.label` is rendered as-is rather than re-worded here. The server
 * builds it with the hedging already baked in ("Likely counts... this is
 * Acadvo's inference, not a statement from your university"), precisely so that
 * a UI cannot accidentally drop the qualifier while re-phrasing. The citations
 * are shown next to it for the same reason.
 *
 * `verdict == null` means no rule covers this course. That renders nothing at
 * all — silence is honest; a grey "does not count" would be a claim nobody made.
 */

const TONE = {
  satisfies: { stated: 'green', inferred: 'yellow' },
  excluded: { stated: 'red', inferred: 'red' },
  no_match: { stated: 'gray', inferred: 'gray' },
};

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export default function BucketVerdict({ verdict, compact = false }) {
  if (!verdict) return null;

  const color = TONE[verdict.outcome]?.[verdict.certainty] || 'gray';
  const chip =
    verdict.outcome === 'satisfies'
      ? verdict.certainty === 'stated'
        ? 'Counts'
        : 'Likely counts'
      : verdict.outcome === 'excluded'
        ? 'Does not count'
        : 'Not covered';

  if (compact) {
    return <Badge color={color} variant="label">{chip}</Badge>;
  }

  const sources = verdict.source_urls || [];

  return (
    <div className="mt-2 rounded-lg border border-dark-700 bg-dark-800/40 p-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge color={color} variant="label">{chip}</Badge>
        {verdict.is_inference && (
          <Badge color="gray" variant="label">Acadvo's inference</Badge>
        )}
        {verdict.stale && <Badge color="gray" variant="label">Needs re-check</Badge>}
      </div>

      {/* Server-authored, hedging included. Do not re-word. */}
      <p className="text-dark-300 text-sm mt-2">{verdict.label}</p>

      {verdict.source_quote && (
        <blockquote className="mt-2 border-l-2 border-dark-600 pl-3 text-dark-400 text-xs italic">
          {verdict.source_quote}
        </blockquote>
      )}

      {sources.length > 0 && (
        <p className="text-xs mt-2">
          <span className="text-dark-500">Source: </span>
          {sources.map((url, i) => (
            <span key={url}>
              {i > 0 && <span className="text-dark-600">, </span>}
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-400 hover:text-primary-300 underline underline-offset-2"
              >
                {hostOf(url)}
              </a>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}
