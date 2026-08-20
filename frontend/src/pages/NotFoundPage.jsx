import { Link } from 'react-router';

/**
 * Real 404, not a redirect.
 *
 * The catch-all used to `<Navigate to="/dashboard">`, which sends a logged-out
 * visitor who mistyped a URL through to /login with no explanation — the app
 * looks broken and the mistyped address is silently lost. A page that says what
 * happened, and offers both a signed-in and a signed-out way out, is the honest
 * answer for a route that does not exist.
 */
export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-dark-950 text-dark-50 flex items-center justify-center p-8">
      <div className="max-w-md text-center">
        <p className="text-sm font-mono uppercase tracking-widest text-dark-400">Error 404</p>
        <h1 className="mt-3 text-3xl font-bold">This page doesn't exist</h1>
        <p className="mt-3 text-dark-300">
          The address you followed isn't a page in Acadvo. It may have moved, or the link may
          have been mistyped.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Link
            to="/dashboard"
            className="px-4 py-2 rounded-lg bg-accent-500 text-dark-950 font-medium text-sm"
          >
            Go to dashboard
          </Link>
          <Link
            to="/"
            className="px-4 py-2 rounded-lg border border-dark-600 text-dark-100 font-medium text-sm"
          >
            Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
