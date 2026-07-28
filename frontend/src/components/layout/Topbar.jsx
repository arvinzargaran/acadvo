import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

const pageTitles = {
  '/dashboard': 'Dashboard',
  '/degree': 'Degree',
  '/schedule': 'Schedule',
  '/courses': 'Course Advisor',
  '/projects': 'Projects',
  '/career': 'Career',
  '/dsa': 'DSA Prep',
  '/study': 'Study Focus',
  '/settings': 'Settings',
};

export default function Topbar({ onMenuToggle }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const title = pageTitles[location.pathname] || 'Acadvo';

  useEffect(() => {
    document.title = title === 'Acadvo' ? 'Acadvo' : `${title} · Acadvo`;
  }, [title]);

  return (
    <header className="h-16 bg-white dark:bg-dark-950 border-b border-gray-200 dark:border-dark-800 flex items-center justify-between px-4 sm:px-8 transition-colors duration-200">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="lg:hidden p-2 text-gray-500 dark:text-dark-400 hover:text-gray-900 dark:hover:text-white transition-colors rounded-lg hover:bg-gray-100 dark:hover:bg-dark-800"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
        <h2 className="text-lg font-semibold text-dark-50 font-display">{title}</h2>
      </div>
      <div className="flex items-center gap-4">
        <button
          onClick={toggleTheme}
          className="p-2 text-gray-500 dark:text-dark-400 hover:text-gray-900 dark:hover:text-white transition-colors rounded-lg hover:bg-gray-100 dark:hover:bg-dark-800"
          title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
        >
          {theme === 'light' ? (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          )}
        </button>
        <span className="text-sm text-gray-600 dark:text-dark-300 hidden sm:inline">{user?.full_name}</span>
        <button
          onClick={handleLogout}
          className="text-sm text-gray-500 dark:text-dark-400 hover:text-gray-900 dark:hover:text-white transition-colors"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
