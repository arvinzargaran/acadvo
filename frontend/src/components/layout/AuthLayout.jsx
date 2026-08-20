import { Link } from 'react-router';

/**
 * Split-screen auth shell — a signage panel (lg+) beside the form column.
 * Collapses to a single centered form column on small screens.
 *
 * Props:
 *  - eyebrow   uppercase tracked label above the title
 *  - title     the form-column heading (string | node)
 *  - children  the form + supporting links
 *  - wide      widen the form column (for the longer register form)
 */
const PROOF = [
  'Track every requirement toward your degree',
  'Plan interview prep and job applications',
  'AI advising tuned to your program',
];

export default function AuthLayout({ eyebrow, title, children, wide = false }) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-2">
      {/* ── Editorial marketing panel (lg+) ── */}
      <aside className="relative hidden lg:flex flex-col justify-between overflow-hidden bg-dark-900 p-12 xl:p-16">
        <div className="aurora-warm absolute inset-0 pointer-events-none" />
        <div className="bg-editorial-grid absolute inset-0 pointer-events-none opacity-70" />

        <Link to="/" className="relative flex items-center gap-2.5 w-fit">
          <span className="wf-bullet wf-bullet-live" style={{ width: '2.25rem', height: '2.25rem', fontSize: '1.1rem' }} aria-hidden="true">
            A
          </span>
          <span className="wf-signage text-xl text-dark-50">Acadvo</span>
        </Link>

        <div className="relative max-w-md">
          <p className="eyebrow mb-5">Built for Canadian students</p>
          <h2 className="wf-display text-4xl xl:text-5xl text-dark-50">
            Your degree is a network.
            <br />
            <span style={{ color: 'var(--wf-line-c-text)' }}>Here is the map.</span>
          </h2>
          <ul className="mt-8 space-y-3.5">
            {PROOF.map((item) => (
              <li key={item} className="flex items-start gap-3 text-dark-200">
                <span
                  aria-hidden="true"
                  className="mt-[0.4rem] shrink-0 rounded-full"
                  style={{
                    width: 9,
                    height: 9,
                    background: 'var(--wf-canvas)',
                    boxShadow: '0 0 0 2.5px var(--wf-live)',
                  }}
                />
                <span className="text-sm leading-snug">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-sm text-dark-400">
          {/* Matches the Service summary on the landing page and the FAQ:
              24 selectable universities in data/universities.js. */}
          <span className="font-semibold text-dark-200">24 universities</span> supported · Free forever
        </p>
      </aside>

      {/* ── Form column ── */}
      <main className="relative flex items-center justify-center px-4 py-10 bg-dark-950 overflow-hidden">
        <div className="aurora-warm absolute inset-0 pointer-events-none lg:hidden" />
        <div className={`relative w-full ${wide ? 'max-w-md' : 'max-w-sm'}`}>
          {/* Mobile wordmark (panel is hidden on small screens) */}
          <Link
            to="/"
            className="lg:hidden mb-8 flex items-center justify-center gap-2.5"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-xl btn-accent font-display text-lg font-bold leading-none">
              A
            </span>
            <span className="text-2xl font-bold font-display text-dark-50 tracking-tight">Acadvo</span>
          </Link>

          <div className="mb-7">
            {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
            <h1 className="font-display text-4xl tracking-tight text-dark-50">{title}</h1>
          </div>

          {children}

          <div className="mt-8">
            <Link to="/" className="text-sm text-dark-400 hover:text-dark-50 transition-colors">
              ← Back to home
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
