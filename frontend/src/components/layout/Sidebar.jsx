import { NavLink } from 'react-router';
import { useAuth } from '../../context/AuthContext';
import Avatar from '../ui/Avatar';

const icons = {
  dashboard: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />,
  schedule: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />,
  degree: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342" />,
  advisor: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />,
  projects: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />,
  career: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0" />,
  dsa: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />,
  study: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />,
  settings: <><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></>,
};

// Nav grouped into labelled sections for structure and scannability.
const navSections = [
  {
    label: 'Overview',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: icons.dashboard },
      { to: '/schedule', label: 'Schedule', icon: icons.schedule },
    ],
  },
  {
    label: 'Academics',
    items: [
      { to: '/degree', label: 'Degree', icon: icons.degree },
      { to: '/courses', label: 'Course Advisor', icon: icons.advisor },
    ],
  },
  {
    label: 'Growth',
    items: [
      { to: '/projects', label: 'Projects', icon: icons.projects },
      { to: '/career', label: 'Career', icon: icons.career },
      { to: '/dsa', label: 'DSA Prep', icon: icons.dsa },
      { to: '/study', label: 'Study Focus', icon: icons.study },
    ],
  },
];

function NavItem({ to, label, icon, onClose }) {
  return (
    <NavLink
      to={to}
      end={to === '/dashboard'}
      onClick={onClose}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
          isActive
            ? 'bg-primary-500/12 text-dark-50'
            : 'text-dark-300 hover:text-dark-50 hover:bg-dark-800/70'
        }`
      }
    >
      {({ isActive }) => (
        <>
          {/* Active indicator rail */}
          <span
            className={`absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r-full bg-primary-500 transition-all ${
              isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-40'
            }`}
          />
          <svg
            className={`w-5 h-5 shrink-0 transition-colors ${isActive ? 'text-primary-500' : 'text-dark-400 group-hover:text-dark-200'}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            {icon}
          </svg>
          {label}
        </>
      )}
    </NavLink>
  );
}

export default function Sidebar({ onClose }) {
  const { user } = useAuth();

  return (
    <aside className="h-screen w-64 bg-dark-900 border-r border-dark-800 flex flex-col transition-colors">
      {/* Wordmark */}
      <div className="px-5 py-5 flex items-center justify-between">
        <NavLink to="/dashboard" onClick={onClose} className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl btn-accent font-display text-lg font-bold leading-none">
            A
          </span>
          <span>
            <span className="block text-xl font-bold font-display text-dark-50 tracking-tight leading-none">
              Acadvo
            </span>
            <span className="block text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-dark-400 mt-0.5">
              Academic Advisor
            </span>
          </span>
        </NavLink>
        {onClose && (
          <button onClick={onClose} className="lg:hidden text-dark-400 hover:text-dark-50 transition-colors" aria-label="Close navigation">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4 space-y-5" data-tour="sidebar-nav">
        {navSections.map((section) => (
          <div key={section.label} className="space-y-1">
            <p className="eyebrow px-3 pb-1 text-[0.62rem]">{section.label}</p>
            {section.items.map((item) => (
              <NavItem key={item.to} {...item} onClose={onClose} />
            ))}
          </div>
        ))}
      </nav>

      {/* User identity footer */}
      <div className="px-3 py-3 border-t border-dark-800">
        <NavLink
          to="/settings"
          onClick={onClose}
          className={({ isActive }) =>
            `flex items-center gap-3 px-2 py-2 rounded-xl transition-colors ${
              isActive ? 'bg-dark-800' : 'hover:bg-dark-800/70'
            }`
          }
        >
          <Avatar name={user?.full_name} size="md" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-dark-50 truncate leading-tight">{user?.full_name || 'Your account'}</p>
            <p className="text-xs text-dark-400 truncate">{user?.email}</p>
          </div>
          <svg className="w-4 h-4 text-dark-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            {icons.settings}
          </svg>
        </NavLink>
      </div>
    </aside>
  );
}
