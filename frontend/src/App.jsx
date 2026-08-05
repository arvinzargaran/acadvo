import { Component } from 'react';
import { Routes, Route, Navigate } from 'react-router';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import ProtectedRoute from './components/layout/ProtectedRoute';
import AppShell from './components/layout/AppShell';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import OnboardingPage from './pages/OnboardingPage';
import DashboardPage from './pages/DashboardPage';
import DegreePage from './pages/DegreePage';
import ProjectsPage from './pages/ProjectsPage';
import CareerPage from './pages/CareerPage';
import DSAPrepPage from './pages/DSAPrepPage';
import CourseAdvisorPage from './pages/CourseAdvisorPage';
import SchedulePage from './pages/SchedulePage';
import StudyPage from './pages/StudyPage';
import SettingsPage from './pages/SettingsPage';

class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-dark-950 flex items-center justify-center p-8">
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 max-w-lg">
            <h2 className="text-red-400 font-bold text-lg mb-2">Something crashed</h2>
            <pre className="text-red-300 text-sm whitespace-pre-wrap break-words">{this.state.error.message}</pre>
            <pre className="text-red-300/50 text-xs mt-2 whitespace-pre-wrap break-words">{this.state.error.stack?.split('\n').slice(0, 5).join('\n')}</pre>
            <button onClick={() => { this.setState({ error: null }); window.location.reload(); }}
              className="mt-4 px-4 py-2 bg-red-500 text-white rounded-lg text-sm">Reload</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <ErrorBoundary>
    <ThemeProvider>
    <AuthProvider>
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
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
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
