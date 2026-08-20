import { motion } from 'framer-motion';

/**
 * The standard heading block for every page, set as a platform sign: a station
 * marker, the section name in expanded caps, and a rule running out to the edge
 * of the measure — then the page title beneath it.
 *
 * Props:
 *  - eyebrow   optional string, rendered as the station name on the sign
 *  - title     string or node, rendered as the display <h1>
 *  - subtitle  optional muted line under the title
 *  - actions   optional node, right-aligned (e.g. buttons)
 *  - className passthrough on the wrapper
 */
export default function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  className = '',
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className={`flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between ${className}`}
    >
      <div className="min-w-0 flex-1">
        {eyebrow && (
          <div className="wf-sign mb-3">
            <span
              aria-hidden="true"
              className="flex-shrink-0 rounded-full"
              style={{
                width: '0.7rem',
                height: '0.7rem',
                background: 'var(--wf-canvas)',
                boxShadow: '0 0 0 2.5px var(--wf-ink)',
              }}
            />
            <p className="wf-signage text-[0.68rem] whitespace-nowrap text-dark-400">
              {eyebrow}
            </p>
          </div>
        )}
        <h1 className="wf-display text-3xl sm:text-4xl text-dark-50">{title}</h1>
        {subtitle && <p className="mt-2 text-dark-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </motion.div>
  );
}
