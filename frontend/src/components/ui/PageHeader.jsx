import { motion } from 'framer-motion';

/**
 * Editorial page header — the standard heading block for every page.
 *
 * Props:
 *  - eyebrow   optional string, rendered as an uppercase tracked brand label
 *  - title     string or node, rendered as the display <h1>
 *  - subtitle  optional muted line under the title
 *  - actions   optional node, right-aligned (e.g. buttons)
 *  - className  passthrough on the wrapper
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
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={`flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between ${className}`}
    >
      <div className="space-y-1.5">
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary-600 dark:text-primary-400">
            {eyebrow}
          </p>
        )}
        <h1 className="font-display text-4xl sm:text-5xl tracking-tight text-dark-50">
          {title}
        </h1>
        {subtitle && <p className="text-dark-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </motion.div>
  );
}
