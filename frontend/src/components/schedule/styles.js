export const CATEGORY_STYLES = {
  course: {
    border: 'border-primary-500/30',
    bg: 'bg-primary-500/10',
    text: 'text-primary-400',
    dot: 'bg-primary-500',
    badge: 'bg-primary-500/20 text-primary-300 border-primary-500/30',
    ring: 'ring-primary-500/40',
    dotSolid: 'bg-primary-500',
  },
  project: {
    border: 'border-emerald-500/30',
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-400',
    dot: 'bg-emerald-500',
    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    ring: 'ring-emerald-500/40',
    dotSolid: 'bg-emerald-500',
  },
  career: {
    border: 'border-amber-500/30',
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
    dot: 'bg-amber-500',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    ring: 'ring-amber-500/40',
    dotSolid: 'bg-amber-500',
  },
};

export function getStyle(cat) {
  return CATEGORY_STYLES[cat] || CATEGORY_STYLES.career;
}

const TZ = 'America/Toronto';

/**
 * Returns YYYY-MM-DD in Toronto timezone (not UTC).
 * This prevents the "off-by-one" bug where toISOString() shifts
 * the date forward after ~8pm ET (midnight UTC).
 */
export function toISODate(d) {
  const parts = d.toLocaleDateString('en-CA', { timeZone: TZ });
  return parts; // en-CA locale gives YYYY-MM-DD
}

/** "Now" as a Date object pinned to Toronto's local midnight for comparisons. */
export function torontoToday() {
  const nowStr = new Date().toLocaleDateString('en-CA', { timeZone: TZ });
  return nowStr; // YYYY-MM-DD string
}

export function daysUntil(dateStr) {
  const todayStr = torontoToday();
  const todayMs = new Date(todayStr + 'T00:00:00').getTime();
  const targetMs = new Date(dateStr + 'T00:00:00').getTime();
  return Math.round((targetMs - todayMs) / (1000 * 60 * 60 * 24));
}

export function daysRemainingBadge(days) {
  if (days < 0) return { label: `${Math.abs(days)}d overdue`, cls: 'bg-red-500/20 text-red-400 border-red-500/30' };
  if (days === 0) return { label: 'Today', cls: 'bg-red-500/20 text-red-400 border-red-500/30' };
  if (days === 1) return { label: 'Tomorrow', cls: 'bg-orange-500/20 text-orange-400 border-orange-500/30' };
  if (days <= 3) return { label: `${days}d left`, cls: 'bg-orange-500/20 text-orange-400 border-orange-500/30' };
  if (days <= 7) return { label: `${days}d left`, cls: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' };
  return { label: `${days}d left`, cls: 'bg-dark-700 text-dark-300 border-dark-600' };
}
