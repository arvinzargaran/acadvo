import { Component, Suspense, lazy } from 'react';
import { Routes, Route } from 'react-router';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import ProtectedRoute from './components/layout/ProtectedRoute';
import Spinner from './components/ui/Spinner';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import NotFoundPage from './pages/NotFoundPage';

// Everything behind auth is code-split.
//
// These pages are only ever reached after a login, but importing them eagerly
// put the whole authenticated app — planner, advisor, PDF export, charts — into
// the one chunk the landing page downloads. A first-time visitor paid for code
// they may never sign up to run. The public entry points (landing, login,
// register) stay eager so the first paint costs no extra round trip.
// AppShell carries the chat widget, which pulls in the markdown renderer; eager
// it would land in the landing page's chunk.
const AppShell = lazy(() => import('./components/layout/AppShell'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'));
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage'));
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const DegreePage = lazy(() => import('./pages/DegreePage'));
const ProjectsPage = lazy(() => import('./pages/ProjectsPage'));
const CareerPage = lazy(() => import('./pages/CareerPage'));
const DSAPrepPage = lazy(() => import('./pages/DSAPrepPage'));
const CourseAdvisorPage = lazy(() => import('./pages/CourseAdvisorPage'));
const SchedulePage = lazy(() => import('./pages/SchedulePage'));
const StudyPage = lazy(() => import('./pages/StudyPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));

function RouteFallback() {
  return (
    <div className="min-h-screen bg-dark-950 flex items-center justify-center" role="status" aria-label="Loading">
      <Spinner className="w-6 h-6 text-primary-500" />
    </div>
  );
}

/**
 * Last line of defence for a render crash.
 *
 * What it deliberately does NOT do is print the exception message and stack to
 * the person using the app. A stack trace names internal modules and can carry
 * fragments of the data being rendered; it is debugging output, and in
 * production it belongs in the console and the error tracker, not on screen.
 * In development it is shown inline, because that is where it is useful.
 */
class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Reaches the browser console, and Sentry's console integration if the
    // frontend is ever wired to one.
    console.error('Unhandled render error', error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="min-h-screen bg-dark-950 flex items-center justify-center p-8">
        <div className="bg-red-500/10 border border-red-500/30 p-6 max-w-lg">
          <h2 className="text-red-400 font-bold text-lg mb-2">Something went wrong</h2>
          <p className="text-dark-200 text-sm">
            This page failed to load. Your data is safe — reloading usually fixes it. If it keeps
            happening, sign out and back in.
          </p>
          {import.meta.env.DEV && (
            <pre className="text-red-300 text-xs mt-4 whitespace-pre-wrap break-words">
              {this.state.error.stack || this.state.error.message}
            </pre>
          )}
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-red-500 text-white text-sm"
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              {/* Public routes */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
              <Route path="/verify-email" element={<VerifyEmailPage />} />

              {/* Onboarding (protected, no shell) */}
              <Route
                path="/onboarding"
                element={
                  <ProtectedRoute>
                    <OnboardingPage />
                  </ProtectedRoute>
                }
              />

              {/* App routes (protected + shell) */}
              <Route
                element={
                  <ProtectedRoute>
                    <AppShell />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/degree" element={<DegreePage />} />
                <Route path="/schedule" element={<SchedulePage />} />
                <Route path="/courses" element={<CourseAdvisorPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/career" element={<CareerPage />} />
                <Route path="/dsa" element={<DSAPrepPage />} />
                <Route path="/study" element={<StudyPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>

              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
          <Toaster
            position="bottom-right"
            toastOptions={{
              // CSS variables so toasts follow the paper/dark theme.
              style: {
                background: 'var(--color-dark-800)',
                color: 'var(--color-dark-50)',
                border: '1px solid var(--color-dark-600)',
              },
              success: {
                iconTheme: { primary: '#10B981', secondary: 'var(--color-dark-800)' },
              },
            }}
          />
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
