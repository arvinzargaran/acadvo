import { Link } from 'react-router-dom';

/**
 * Split-screen auth shell — an editorial marketing panel (lg+) beside the
 * form column. Collapses to a single centered form column on small screens.
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
          <span className="flex h-10 w-10 items-center justify-center rounded-xl btn-accent font-display text-xl font-bold leading-none">
            A
          </span>
          <span className="text-2xl font-bold font-display text-dark-50 tracking-tight">Acadvo</span>
        </Link>

        <div className="relative max-w-md">
          <p className="eyebrow mb-4">Built for Canadian students</p>
          <h2 className="font-display text-4xl xl:text-5xl leading-[1.05] tracking-tight text-dark-50">
            Graduate on time.
            <br />
            <span className="text-gradient-warm">Land the internship.</span>
          </h2>
          <ul className="mt-8 space-y-3.5">
            {PROOF.map((item) => (
              <li key={item} className="flex items-start gap-3 text-dark-200">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary-500/15 ring-1 ring-inset ring-primary-500/30">
                  <svg className="h-3 w-3 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </span>
                <span className="text-sm leading-snug">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-sm text-dark-400">
          <span className="font-semibold text-dark-200">25+ universities</span> supported · Free forever
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
