import { useId } from 'react';
import { Link, useLocation } from 'react-router';
import Logo from '../components/brand/Logo';

/**
 * Shared shell for /privacy and /terms.
 *
 * Deliberately plain and deliberately public: these pages must be readable
 * before anyone has an account, must survive being printed, and must not depend
 * on the app shell (which is behind auth). Body text is a real prose measure,
 * not the app's dense dashboard scale — nobody has ever been helped by a privacy
 * policy set in 12px.
 */
export function LegalPage({ eyebrow, title, summary, updated, children }) {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen" style={{ background: 'var(--wf-canvas)', color: 'var(--wf-ink)' }}>
      <header className="px-6 py-5" style={{ borderBottom: '2px solid var(--wf-ink)' }}>
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2.5">
            <Logo size="1.5rem" />
            <span className="wf-signage text-sm">acadvo</span>
          </Link>
          {/* Two links that differ only by one word need the current one marked:
              without it a screen reader reads the same pair on both documents
              with nothing to say which one is open. */}
          <nav className="flex items-center gap-5" aria-label="Legal documents">
            <Link
              to="/privacy"
              aria-current={pathname === '/privacy' ? 'page' : undefined}
              className="wf-signage text-[10px]"
              style={{ color: 'var(--wf-muted)' }}
            >
              Privacy
            </Link>
            <Link
              to="/terms"
              aria-current={pathname === '/terms' ? 'page' : undefined}
              className="wf-signage text-[10px]"
              style={{ color: 'var(--wf-muted)' }}
            >
              Terms
            </Link>
          </nav>
        </div>
      </header>

      <main className="px-6 py-12">
        <article className="max-w-3xl mx-auto">
          <p className="wf-signage text-[10px]" style={{ color: 'var(--wf-muted)' }}>{eyebrow}</p>
          <h1 className="mt-3 text-3xl md:text-4xl font-bold tracking-tight">{title}</h1>
          <p className="mt-4 text-base leading-relaxed" style={{ color: 'var(--wf-muted)' }}>
            {summary}
          </p>
          <p className="mt-2 text-sm" style={{ color: 'var(--wf-muted)' }}>
            Last updated {updated}.
          </p>

          <div className="mt-10 space-y-9">{children}</div>

          <p className="mt-14 pt-6 text-sm" style={{ borderTop: '1px solid var(--wf-rule)', color: 'var(--wf-muted)' }}>
            <Link to="/" className="underline">Back to acadvo</Link>
          </p>
        </article>
      </main>
    </div>
  );
}

/** One numbered section. The heading is a real `h2` so screen readers can jump. */
export function Section({ id, heading, children }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`} className="text-lg font-bold tracking-tight">
        {heading}
      </h2>
      <div className="mt-3 space-y-3 text-[15px] leading-relaxed" style={{ color: 'var(--wf-muted)' }}>
        {children}
      </div>
    </section>
  );
}

/** A table of what is collected and why — clearer than a wall of prose. */
export function DataTable({ rows }) {
  const captionId = useId();

  return (
    // The table keeps its own horizontal scroll so a narrow phone never scrolls
    // the whole document sideways. A scrollable box is also a keyboard trap in
    // reverse — unreachable without a pointer — so it takes a tab stop and a
    // name of its own (WCAG 2.1.1, and 1.3.1 for the region label).
    /* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex --
       the rule allows a tab stop only on role="tabpanel". */
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-labelledby={captionId}>
      <table className="w-full text-left text-sm border-collapse">
        <caption id={captionId} className="sr-only">
          Personal information collected, and the purpose of each
        </caption>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--wf-ink)' }}>
            <th scope="col" className="py-2 pr-4 wf-signage text-[10px]" style={{ color: 'var(--wf-ink)' }}>
              What
            </th>
            <th scope="col" className="py-2 pr-4 wf-signage text-[10px]" style={{ color: 'var(--wf-ink)' }}>
              Why
            </th>
            <th scope="col" className="py-2 wf-signage text-[10px]" style={{ color: 'var(--wf-ink)' }}>
              Kept until
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.what} style={{ borderBottom: '1px solid var(--wf-rule)' }}>
              <th scope="row" className="py-3 pr-4 font-medium align-top" style={{ color: 'var(--wf-ink)' }}>
                {row.what}
              </th>
              <td className="py-3 pr-4 align-top">{row.why}</td>
              <td className="py-3 align-top">{row.kept}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
