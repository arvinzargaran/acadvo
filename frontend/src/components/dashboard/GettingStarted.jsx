import { motion, useReducedMotion } from 'framer-motion';
import { Link } from 'react-router-dom';

// ── Step icons ───────────────────────────────────────────────────

const ICONS = {
  degree: 'M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z',
  projects: 'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4',
  career: 'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  advisor: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
};

// ── One checklist row ────────────────────────────────────────────

function Step({ icon, title, description, done, index, prefersReduced, ...action }) {
  const inner = (
    <>
      <div
        className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center border transition-colors ${
          done
            ? 'bg-green-500/15 border-green-500/30 text-green-500 dark:text-green-400'
            : 'bg-primary-500/10 border-primary-500/20 text-primary-600 dark:text-primary-400 group-hover:bg-primary-500/20'
        }`}
      >
        {done ? (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d={icon} />
          </svg>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-semibold ${done ? 'text-gray-400 dark:text-dark-400 line-through' : 'text-gray-900 dark:text-white'}`}>
          {title}
        </p>
        <p className="text-gray-500 dark:text-dark-400 text-xs mt-0.5 leading-snug">{description}</p>
      </div>
      {!done && (
        <svg className="w-4 h-4 flex-shrink-0 text-gray-300 dark:text-dark-500 group-hover:text-primary-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      )}
    </>
  );

  const cls =
    'group flex items-center gap-3 rounded-2xl px-3 py-3 border border-gray-100 dark:border-white/5 bg-gray-50 dark:bg-white/5 hover:border-primary-500/30 dark:hover:border-primary-500/30 hover:bg-white dark:hover:bg-white/10 transition-all text-left w-full';

  const interactive = action.to ? (
    <Link to={action.to} className={cls}>
      {inner}
    </Link>
  ) : (
    <button type="button" onClick={action.onClick} className={cls}>
      {inner}
    </button>
  );

  if (prefersReduced) return interactive;

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, delay: 0.15 + index * 0.07, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      {interactive}
    </motion.div>
  );
}

// ── Getting started checklist ─────────────────────────────────────

export default function GettingStarted({ hasDegree, hasProjects, hasCareer, className = '' }) {
  const prefersReduced = useReducedMotion();

  const steps = [
    {
      icon: ICONS.degree,
      title: 'Import your degree checklist',
      description: 'Upload your program requirements so we can track credits and GPA.',
      done: hasDegree,
      to: '/degree',
    },
    {
      icon: ICONS.projects,
      title: 'Add your first project',
      description: 'Showcase what you are building to boost your co-op readiness.',
      done: hasProjects,
      to: '/projects',
    },
    {
      icon: ICONS.career,
      title: 'Set a career target',
      description: 'Pick a role you are aiming for and we will map the path.',
      done: hasCareer,
      to: '/career',
    },
    {
      icon: ICONS.advisor,
      title: 'Ask the AI advisor',
      description: 'Tap the chat bubble in the bottom-right corner anytime for guidance.',
      done: false,
      onClick: () => window.dispatchEvent(new CustomEvent('open-chat-widget')),
    },
  ];

  const completed = steps.filter((s) => s.done).length;

  return (
    <motion.div
      initial={prefersReduced ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={`relative overflow-hidden bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl p-6 shadow-sm ${className}`}
      data-tour="getting-started"
    >
      {/* Warm accent glow */}
      <div className="pointer-events-none absolute -top-16 -right-16 w-48 h-48 rounded-full bg-primary-500/10 blur-3xl" />

      <div className="relative">
        <div className="flex items-start justify-between gap-4 mb-1">
          <div>
            <p className="text-primary-600 dark:text-primary-400 text-xs font-semibold uppercase tracking-widest mb-1">
              Welcome to Acadvo
            </p>
            <h2 className="font-display text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white tracking-tight">
              Let's get you set up
            </h2>
          </div>
          <span className="flex-shrink-0 text-xs font-semibold text-gray-500 dark:text-dark-400 bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-full px-3 py-1 tabular-nums">
            {completed}/{steps.length}
          </span>
        </div>
        <p className="text-gray-500 dark:text-dark-400 text-sm mb-5 max-w-xl">
          Your dashboard comes alive once you add a little data. Knock out these steps to unlock your co-op readiness score, milestones, and personalized insights.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {steps.map((step, i) => (
            <Step key={step.title} index={i} prefersReduced={prefersReduced} {...step} />
          ))}
        </div>
      </div>
    </motion.div>
  );
}
