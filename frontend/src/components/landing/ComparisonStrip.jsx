import { motion, useReducedMotion } from 'framer-motion';

// ─── Motion ────────────────────────────────────────────────────────────────
const ease = [0.16, 1, 0.3, 1];

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: (delay = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay, ease },
  }),
};

// ─── Icons ─────────────────────────────────────────────────────────────────
function CheckIcon({ className = '' }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={`w-[18px] h-[18px] ${className}`} aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
        clipRule="evenodd"
      />
    </svg>
  );
}

// ─── Data ──────────────────────────────────────────────────────────────────
// value kinds: 'yes' | 'no' | { partial: 'label' } | { text: 'label' }
const COLUMNS = [
  { key: 'sheet', label: 'A spreadsheet' },
  { key: 'apps', label: '5 separate apps' },
  { key: 'acadvo', label: 'Acadvo', accent: true },
];

const ROWS = [
  {
    label: 'Degree & prerequisite tracking',
    values: [{ partial: 'Manual' }, 'no', 'yes'],
  },
  {
    label: 'GPA simulation',
    values: [{ partial: 'Partial' }, 'no', 'yes'],
  },
  {
    label: 'Application pipeline',
    values: ['no', { partial: 'Scattered' }, 'yes'],
  },
  {
    label: 'AI course advice',
    values: ['no', 'no', 'yes'],
  },
  {
    label: 'Interview prep',
    values: ['no', { partial: 'Partial' }, 'yes'],
  },
  {
    label: 'Everything in one place',
    values: ['no', 'no', 'yes'],
  },
  {
    label: 'Price',
    values: [{ text: 'Free-ish*' }, { text: 'Adds up' }, { text: 'Free forever' }],
  },
];

// ─── Value cell ────────────────────────────────────────────────────────────
function ValueCell({ value, accent }) {
  if (value === 'yes') {
    return (
      <span className="inline-flex items-center justify-center">
        <CheckIcon className={accent ? 'text-primary-600' : 'text-emerald-600'} />
        <span className="sr-only">Yes</span>
      </span>
    );
  }
  if (value === 'no') {
    return (
      <span className="text-dark-400 text-base leading-none" aria-label="No">
        &ndash;
      </span>
    );
  }
  if (value && value.partial) {
    return (
      <span className="text-dark-400 text-xs tracking-wide">{value.partial}</span>
    );
  }
  if (value && value.text) {
    return (
      <span
        className={
          accent
            ? 'font-display text-primary-600 text-sm md:text-base'
            : 'text-dark-300 text-sm'
        }
      >
        {value.text}
      </span>
    );
  }
  return null;
}

// ─── Section ───────────────────────────────────────────────────────────────
export default function ComparisonStrip() {
  const reduced = useReducedMotion();
  const viewport = { once: true, margin: '-80px' };

  return (
    <div>
      <div>
        {/* Header */}
        <motion.div
          initial={reduced ? false : 'hidden'}
          whileInView="visible"
          viewport={viewport}
          variants={fadeUp}
          custom={0}
        >
          <h2 className="font-display font-bold text-dark-50 tracking-tight text-4xl md:text-5xl leading-[1.05]">
            One place, not{' '}
            <span className="font-display text-gradient-warm">fifteen.</span>
          </h2>
          <p className="text-dark-400 text-lg mt-5 max-w-xl">
            One spreadsheet gone stale, five apps that never talk to each other, or
            everything pulling in the same direction.
          </p>
        </motion.div>

        {/* Table */}
        <motion.div
          initial={reduced ? false : 'hidden'}
          whileInView="visible"
          viewport={viewport}
          variants={fadeUp}
          custom={0.1}
          className="mt-14 overflow-x-auto -mx-6 px-6"
        >
          <div className="min-w-[560px]">
            <table className="w-full border-collapse table-fixed">
              <colgroup>
                <col className="w-[34%]" />
                <col className="w-[22%]" />
                <col className="w-[22%]" />
                <col className="w-[22%]" />
              </colgroup>

              {/* Header row */}
              <thead>
                <tr>
                  <th className="text-left align-bottom pb-4 pr-4">
                    <span className="text-[11px] tracking-[0.22em] uppercase text-dark-400">
                      Capability
                    </span>
                  </th>
                  {COLUMNS.map((col) =>
                    col.accent ? (
                      <th key={col.key} className="p-0 align-bottom">
                        <div className="card-rich bg-primary-500/5 border-x border-t border-primary-500/25 rounded-t-2xl px-2 py-4 text-center">
                          <span className="font-display text-primary-700 text-base md:text-lg font-semibold">
                            {col.label}
                          </span>
                        </div>
                      </th>
                    ) : (
                      <th
                        key={col.key}
                        className="text-center align-bottom pb-4 px-2"
                      >
                        <span className="text-dark-300 text-sm md:text-base">
                          {col.label}
                        </span>
                      </th>
                    ),
                  )}
                </tr>
              </thead>

              <tbody>
                {ROWS.map((row, rowIdx) => {
                  const isLast = rowIdx === ROWS.length - 1;
                  return (
                    <tr key={row.label}>
                      <td
                        className={`text-left py-4 pr-4 border-b border-dark-600/60 ${
                          isLast ? 'border-b-0' : ''
                        }`}
                      >
                        <span className="text-dark-300 text-sm md:text-[15px]">
                          {row.label}
                        </span>
                      </td>
                      {row.values.map((value, colIdx) => {
                        const accent = COLUMNS[colIdx].accent;
                        return (
                          <td
                            key={COLUMNS[colIdx].key}
                            className={`text-center py-4 px-2 border-b border-dark-600/60 ${
                              isLast ? 'border-b-0' : ''
                            } ${
                              accent
                                ? `bg-primary-500/5 border-x border-primary-500/25 ${
                                    isLast ? 'border-b border-primary-500/25 rounded-b-2xl' : ''
                                  }`
                                : ''
                            }`}
                          >
                            <ValueCell value={value} accent={accent} />
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </motion.div>

        <motion.p
          initial={reduced ? false : 'hidden'}
          whileInView="visible"
          viewport={viewport}
          variants={fadeUp}
          custom={0.15}
          className="text-[11px] text-dark-400 mt-5"
        >
          * Free until you factor in the hours spent keeping it current.
        </motion.p>
      </div>
    </div>
  );
}
