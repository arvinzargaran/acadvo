import { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

/**
 * FolioRail — a fixed, editorial "folio" / section-index rail down the left
 * margin. Tracks scroll position via an IntersectionObserver so the item whose
 * section currently occupies the viewport center reads as active. Desktop-only,
 * quiet, and small.
 *
 * @param {{ items: Array<{ id: string, n: string, label: string }> }} props
 *   `id`    — the DOM id of the target <section>
 *   `n`     — a two-digit string like "01"
 *   `label` — a short name
 */
export default function FolioRail({ items = [], hidden = false }) {
  const [activeId, setActiveId] = useState(null);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!items.length) return undefined;

    // Only observe sections that are actually mounted — a section may be absent.
    const targets = items
      .map(({ id }) => document.getElementById(id))
      .filter(Boolean);

    if (!targets.length) return undefined;

    // Bias the root so a section becomes "active" while it crosses the
    // viewport's vertical center band.
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        });
      },
      { rootMargin: '-45% 0px -45% 0px', threshold: 0 }
    );

    targets.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [items]);

  const handleClick = (id) => {
    document.getElementById(id)?.scrollIntoView({
      behavior: reduceMotion ? 'auto' : 'smooth',
      block: 'start',
    });
  };

  if (!items.length) return null;

  return (
    <nav
      aria-label="Section index"
      className={`fixed left-6 xl:left-8 top-1/2 -translate-y-1/2 z-40 hidden 2xl:flex flex-col gap-3 pointer-events-none transition-opacity duration-500 ${
        hidden ? 'opacity-0 invisible' : 'opacity-100'
      }`}
    >
      {items.map(({ id, n, label }) => {
        const isActive = id === activeId;

        return (
          <button
            key={id}
            type="button"
            onClick={() => handleClick(id)}
            aria-current={isActive ? 'true' : undefined}
            className="pointer-events-auto group flex items-center gap-3 text-left focus:outline-none focus-visible:ring-1 focus-visible:ring-primary-500 rounded-sm"
          >
            {/* Leading hairline marker — grows and warms when active. */}
            <motion.span
              aria-hidden="true"
              className="block h-px shrink-0 rounded-full"
              initial={false}
              animate={{
                width: isActive ? 24 : 10,
                opacity: isActive ? 1 : 0.4,
                backgroundColor: isActive
                  ? 'rgb(240 126 0)' // primary-600
                  : 'rgb(115 115 115)', // faint marker
              }}
              transition={
                reduceMotion
                  ? { duration: 0 }
                  : { type: 'spring', stiffness: 380, damping: 32 }
              }
            />

            <span className="flex items-baseline gap-2">
              <motion.span
                className="font-display text-sm leading-none tabular-nums"
                initial={false}
                animate={{ opacity: isActive ? 1 : 0.55 }}
                transition={reduceMotion ? { duration: 0 } : { duration: 0.3 }}
                style={{
                  color: isActive ? 'rgb(240 126 0)' : undefined,
                }}
              >
                <span className={isActive ? '' : 'text-dark-400'}>{n}</span>
              </motion.span>

              <motion.span
                className="text-[10px] tracking-[0.22em] uppercase leading-none whitespace-nowrap"
                initial={false}
                animate={{ opacity: isActive ? 1 : 0.6 }}
                transition={reduceMotion ? { duration: 0 } : { duration: 0.3 }}
              >
                <span
                  className={
                    isActive
                      ? 'text-dark-50'
                      : 'text-dark-400 group-hover:text-dark-500 transition-colors'
                  }
                >
                  {label}
                </span>
              </motion.span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
