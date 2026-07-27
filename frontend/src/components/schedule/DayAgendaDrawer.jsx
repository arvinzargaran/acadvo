import { motion, AnimatePresence } from 'framer-motion';
import { getStyle, daysUntil, daysRemainingBadge } from './styles';

const CATEGORY_ACTIONS = {
  course: { label: 'View Course', href: '/degree' },
  project: { label: 'View Project', href: '/projects' },
  career: { label: 'View Career', href: '/career' },
};

export default function DayAgendaDrawer({ dateKey, events, onClose }) {
  const isOpen = !!dateKey;

  const dateLabel = dateKey
    ? new Date(dateKey + 'T12:00:00').toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
      })
    : '';

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Dimming overlay */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-md bg-dark-900/95 backdrop-blur-2xl border-l border-white/10 shadow-2xl flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
              <div>
                <p className="text-dark-400 text-xs font-semibold uppercase tracking-widest">Agenda</p>
                <h2 className="text-white text-lg font-bold mt-0.5">{dateLabel}</h2>
              </div>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center text-dark-400 hover:text-white transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Event list */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
              {(!events || events.length === 0) ? (
                <div className="flex flex-col items-center justify-center h-full text-center py-12">
                  <svg className="w-12 h-12 text-dark-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <p className="text-dark-400 text-sm">Nothing scheduled for this day</p>
                  <p className="text-dark-500 text-xs mt-1">Enjoy the free time!</p>
                </div>
              ) : (
                events.map(event => <AgendaCard key={event.id} event={event} />)
              )}
            </div>

            {/* Footer */}
            {events && events.length > 0 && (
              <div className="px-6 py-4 border-t border-white/5">
                <p className="text-dark-500 text-xs">
                  {events.length} item{events.length !== 1 ? 's' : ''} on this day
                </p>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function AgendaCard({ event }) {
  const s = getStyle(event.category);
  const days = event.date ? daysUntil(event.date) : null;
  const badge = days !== null ? daysRemainingBadge(days) : null;
  const action = CATEGORY_ACTIONS[event.category] || CATEGORY_ACTIONS.career;

  return (
    <div className={`group rounded-xl border ${s.border} bg-white/[0.03] hover:bg-white/[0.06] backdrop-blur-sm p-4 transition-all duration-200`}>
      {/* Top row: accent bar + content */}
      <div className="flex gap-3">
        <div className={`w-1 rounded-full ${s.dot} flex-shrink-0 self-stretch`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className="text-white text-sm font-semibold">{event.title}</p>
            {event.weight != null && (
              <span className={`text-xs font-bold ${s.text} flex-shrink-0`}>{event.weight}%</span>
            )}
          </div>

          {/* Meta row */}
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className={`text-[10px] px-2 py-0.5 rounded-full border ${s.badge} capitalize`}>
              {event.category}
            </span>
            {event.type && (
              <span className="text-dark-500 text-[10px]">{event.type}</span>
            )}
            {badge && (
              <span className={`text-[10px] px-2 py-0.5 rounded-full border ${badge.cls}`}>{badge.label}</span>
            )}
          </div>

          {/* Notes */}
          {event.notes && (
            <p className="text-dark-400 text-xs mt-2 leading-relaxed">{event.notes}</p>
          )}

          {/* Quick action */}
          <a
            href={action.href}
            className={`inline-flex items-center gap-1 mt-3 text-xs font-medium ${s.text} opacity-0 group-hover:opacity-100 transition-opacity duration-200`}
          >
            {action.label}
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </a>
        </div>
      </div>
    </div>
  );
}
