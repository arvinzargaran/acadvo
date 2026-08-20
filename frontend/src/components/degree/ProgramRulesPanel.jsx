import { useEffect, useState } from 'react';
import Badge from '../ui/Badge';
import Spinner from '../ui/Spinner';
import { getProgramRules, refreshProgramRules, researchProgramRules } from '../../api/courseAdvisor';
import toast from 'react-hot-toast';

/**
 * "What does Acadvo know about my program's requirements, and how does it know?"
 *
 * Mounting this is also what asks the server to research an uncovered program,
 * which is how coverage grows: from a real student opening the page, not from
 * anyone maintaining a list. The request returns immediately — the research runs
 * in the background — so this never blocks the page.
 *
 * Every state renders a sentence. A blank panel would read as "nothing counts
 * toward your degree", which is a claim nobody made.
 */

const STATE_TONE = {
  ready: 'green',
  researching: 'blue',
  needs_url: 'yellow',
  not_started: 'gray',
  failed: 'yellow',
  empty: 'yellow',
  unavailable: 'gray',
};

const STATE_LABEL = {
  ready: 'Requirements loaded',
  researching: 'Reading your university',
  needs_url: 'Needs your requirements page',
  not_started: 'Not looked up yet',
  failed: 'Could not read',
  empty: 'Nothing verifiable found',
  unavailable: 'Not configured',
};

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export default function ProgramRulesPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [url, setUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    try {
      const { data } = await getProgramRules();
      setData(data);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  // Research takes tens of seconds and finishes without telling anyone, so poll
  // while it is in flight — but only while it is in flight, and stop when the
  // component unmounts so a backgrounded tab isn't polling forever.
  useEffect(() => {
    if (data?.state !== 'researching') return undefined;
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [data?.state]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await refreshProgramRules();
      toast.success('Queued — requirement rules will refresh shortly.');
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not queue a refresh.');
    } finally {
      setRefreshing(false);
    }
  }

  async function handleSubmitUrl(e) {
    e.preventDefault();
    if (!url.trim()) return;
    setSubmitting(true);
    try {
      await researchProgramRules(url.trim());
      toast.success("Queued — Acadvo is reading your program's requirements.");
      setUrl('');
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not queue that page.');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-dark-400 text-sm">
        <Spinner className="w-4 h-4 text-primary-400" />
        Checking your program's requirements...
      </div>
    );
  }
  if (!data) return null;

  const buckets = data.buckets || [];

  return (
    <div className="rounded-xl border border-dark-700 bg-dark-800/40 p-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge color={STATE_TONE[data.state] || 'gray'} dot>
            {STATE_LABEL[data.state] || data.state}
          </Badge>
          {data.stale && <Badge color="yellow" variant="label">Needs re-check</Badge>}
          <span className="text-dark-300 text-sm">
            {data.program} · {data.university}
          </span>
        </div>
        {data.research_enabled && (
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="text-xs text-dark-400 hover:text-dark-50 transition-colors disabled:opacity-50"
          >
            {refreshing ? 'Queueing...' : 'Re-check requirements'}
          </button>
        )}
      </div>

      <p className="text-dark-400 text-sm mt-2">{data.message}</p>

      {(data.state === 'needs_url' || data.state === 'failed') && data.research_enabled && (
        <form onSubmit={handleSubmitUrl} className="mt-3 flex gap-2 flex-wrap">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://your-university.ca/.../program-requirements"
            aria-label="Official program requirements page URL"
            className="flex-1 min-w-[16rem] bg-dark-800 border border-dark-600 text-dark-50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <button
            type="submit"
            disabled={submitting || !url.trim()}
            className="text-xs bg-primary-500/20 text-primary-300 hover:bg-primary-500/30 px-3 py-2 rounded-lg transition-colors disabled:opacity-50"
          >
            {submitting ? 'Queueing...' : 'Read this page'}
          </button>
        </form>
      )}

      {data.job?.last_error && data.state === 'failed' && (
        <p className="text-dark-500 text-xs mt-1">Details: {data.job.last_error}</p>
      )}

      {buckets.length > 0 && (
        <>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-primary-400 hover:text-primary-300 mt-3 transition-colors"
          >
            {expanded ? 'Hide' : `Show ${buckets.length} requirement rule${buckets.length === 1 ? '' : 's'}`}
          </button>

          {expanded && (
            <ul className="mt-3 space-y-3">
              {buckets.map((b) => (
                <li key={b.bucket_name} className="border-l-2 border-dark-600 pl-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-dark-50 text-sm font-medium">{b.bucket_name}</span>
                    {b.credits_required != null && (
                      <span className="text-dark-500 text-xs">{b.credits_required} credits</span>
                    )}
                    {/* Spelled out in words, not left to a colour: this is the
                        difference between the university's word and ours. */}
                    <Badge color={b.basis === 'stated' ? 'green' : 'yellow'} variant="label">
                      {b.basis_label}
                    </Badge>
                  </div>
                  {b.allowed_subjects?.length > 0 && (
                    <p className="text-dark-400 text-xs mt-1">
                      Accepts: {b.allowed_subjects.join(', ')}
                      {b.level_floor ? ` at ${b.level_floor}-level or above` : ''}
                    </p>
                  )}
                  {b.excluded_codes?.length > 0 && (
                    <p className="text-dark-400 text-xs mt-1">
                      Explicitly excluded: {b.excluded_codes.join(', ')}
                    </p>
                  )}
                  {b.source_quote && (
                    <blockquote className="mt-1 text-dark-500 text-xs italic">
                      "{b.source_quote}"
                    </blockquote>
                  )}
                  {b.source_urls?.length > 0 && (
                    <p className="text-xs mt-1">
                      {b.source_urls.map((url, i) => (
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
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
