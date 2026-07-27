import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Spinner from '../ui/Spinner';

export default function ProtectedRoute({ children }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Spinner className="w-10 h-10 text-primary-500" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!user?.onboarding_complete && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  if (user?.onboarding_complete && location.pathname === '/onboarding') {
    return <Navigate to="/dashboard" replace />;
  }

  return children || <Outlet />;
}
