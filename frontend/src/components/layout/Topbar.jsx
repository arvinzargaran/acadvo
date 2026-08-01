import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import Avatar from '../ui/Avatar';

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
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const title = pageTitles[location.pathname] || 'Acadvo';

  useEffect(() => {
    document.title = title === 'Acadvo' ? 'Acadvo' : `${title} · Acadvo`;
  }, [title]);

  // Close the user menu on outside click / Escape.
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    const onKey = (e) => e.key === 'Escape' && setMenuOpen(false);
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  return (
    <header className="sticky top-0 z-30 h-16 border-b border-dark-800 bg-dark-900/80 backdrop-blur-md flex items-center justify-between px-4 sm:px-8 transition-colors duration-200 supports-[backdrop-filter]:bg-dark-900/70">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuToggle}
          className="lg:hidden p-2 -ml-2 text-dark-400 hover:text-dark-50 transition-colors rounded-lg hover:bg-dark-800"
          aria-label="Open navigation"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
        {/* Breadcrumb: sticky context once the page's editorial header scrolls away. */}
        <nav className="flex items-center gap-2 min-w-0 text-sm" aria-label="Breadcrumb">
          <span className="hidden sm:inline text-dark-400">Acadvo</span>
          <svg className="hidden sm:block w-3.5 h-3.5 text-dark-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <span className="font-semibold text-dark-50 font-display tracking-tight truncate">{title}</span>
        </nav>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          onClick={toggleTheme}
          className="p-2 text-dark-400 hover:text-dark-50 transition-colors rounded-lg hover:bg-dark-800"
          title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          aria-label="Toggle theme"
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

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((o) => !o)}
            className="flex items-center gap-2 pl-1.5 pr-2 py-1.5 rounded-full hover:bg-dark-800 transition-colors"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
          >
            <Avatar name={user?.full_name} size="sm" />
            <span className="hidden sm:inline text-sm font-medium text-dark-200 max-w-[10rem] truncate">
              {user?.full_name}
            </span>
            <svg className={`hidden sm:block w-4 h-4 text-dark-400 transition-transform ${menuOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>

          {menuOpen && (
            <div
              role="menu"
              className="absolute right-0 mt-2 w-60 origin-top-right rounded-xl border border-dark-600 bg-dark-800 shadow-editorial ring-1 ring-black/5 dark:ring-white/10 overflow-hidden animate-[scaleIn_0.14s_ease-out]"
            >
              <div className="flex items-center gap-3 px-4 py-3.5 border-b border-dark-700">
                <Avatar name={user?.full_name} size="md" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-dark-50 truncate">{user?.full_name}</p>
                  <p className="text-xs text-dark-400 truncate">{user?.email}</p>
                </div>
              </div>
              <div className="p-1.5">
                <Link
                  to="/settings"
                  onClick={() => setMenuOpen(false)}
                  role="menuitem"
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-dark-200 hover:bg-dark-700 hover:text-dark-50 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                  Settings
                </Link>
                <button
                  onClick={handleLogout}
                  role="menuitem"
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-dark-200 hover:bg-dark-700 hover:text-dark-50 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" /></svg>
                  Log out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
