import { useState, useEffect, useId } from 'react';
import { createPortal } from 'react-dom';
import { motion, useSpring, useTransform } from 'framer-motion';
import Card from '../ui/Card';
import { getReadiness } from '../../api/users';

const CATEGORY_META = {
  gpa: { label: 'GPA', icon: 'M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z' },
  projects: { label: 'Projects', icon: 'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4' },
  dsa: { label: 'DSA', icon: 'M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z' },
  career: { label: 'Career', icon: 'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
};

function getTierLabel(score) {
  if (score >= 61) return 'Interview Ready';
  if (score >= 31) return 'Competitive Candidate';
  return 'Foundation Phase';
}

function getTierColor(score) {
  if (score >= 61) return '#2f9e6e';
  if (score >= 31) return '#d98200';
  return '#8A7C63';
}

const TIPS = {
  gpa: 'Boost your GPA by focusing on high-weight courses this term.',
  projects: 'Deploy a project to production to gain points.',
  dsa: 'Solve 3+ problems in a new pattern to level up.',
  career: 'Add career targets or get your resume reviewed.',
};

function getSmartTip(breakdown) {
  if (!breakdown) return null;
  let weakest = null;
  let lowestPct = Infinity;
  for (const [key, cat] of Object.entries(breakdown)) {
    const pct = cat.max > 0 ? cat.score / cat.max : 1;
    if (pct < lowestPct) {
      lowestPct = pct;
      weakest = key;
    }
  }
  return weakest ? TIPS[weakest] : null;
}

// ── Animated SVG Ring ────────────────────────────────────────────

function GlowRing({ value, size = 160, showText = true }) {
  const gradId = useId();
  const filterId = useId();
  const strokeWidth = Math.max(4, Math.floor(size / 16));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Spring-animated progress
  const spring = useSpring(0, { stiffness: 60, damping: 18, mass: 1.2 });
  const offset = useTransform(spring, (v) => circumference - (v / 100) * circumference);

  // Animated display number
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    spring.set(Math.min(100, Math.max(0, value)));
    const unsub = spring.on('change', (v) => setDisplay(Math.round(v)));
    return unsub;
  }, [value, spring]);

  let numSize = 'text-4xl';
  let pctSize = 'text-lg';
  if (size < 100) {
    numSize = 'text-2xl';
    pctSize = 'text-sm';
  }
  if (size < 75) {
    numSize = 'text-xl';
    pctSize = 'text-xs';
  }

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#FF8A00" />
            <stop offset="100%" stopColor="#F07E00" />
          </linearGradient>
          <filter id={filterId}>
            <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor="rgba(255,138,0,0.45)" />
          </filter>
        </defs>
        {/* Track */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="rgba(36,30,21,0.12)" strokeWidth={strokeWidth}
        />
        {/* Animated arc */}
        <motion.circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          style={{ strokeDashoffset: offset }}
          filter={`url(#${filterId})`}
        />
      </svg>
      {/* Center text */}
      {showText && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`${numSize} font-extrabold text-white tabular-nums leading-none`}>
            {display}
            <span className={`${pctSize} font-normal text-dark-400`}>%</span>
          </span>
        </div>
      )}
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────

export default function ReadinessScore({ bento = false }) {
  const [data, setData] = useState(null);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    getReadiness()
      .then(res => setData(res.data))
      .catch(() => setData(null));
  }, []);

  if (!data) return null;

  const tierLabel = getTierLabel(data.total);
  const tierColor = getTierColor(data.total);
  const tip = getSmartTip(data.breakdown);

  // ── Bento hero layout ──────────────────────────────────────────

  if (bento) {
    return (
      <>
        <motion.div
          onClick={() => setShowModal(true)}
          className="h-full flex flex-col cursor-pointer"
          animate={{ scale: [1, 1.01, 1] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        >
          <p className="text-dark-400 text-xs font-semibold uppercase tracking-widest mb-4">Co-op Readiness</p>

          <div className="flex-1 flex items-center gap-8">
            {/* Ring */}
            <GlowRing value={data.total} size={160} />

            {/* Right side */}
            <div className="flex-1 min-w-0">
              <p className="font-bold text-lg mb-4" style={{ color: tierColor }}>{tierLabel}</p>

              {/* Category bars */}
              <div className="space-y-3">
                {Object.entries(data.breakdown).map(([key, cat]) => {
                  const pct = cat.max > 0 ? (cat.score / cat.max) * 100 : 0;
                  const meta = CATEGORY_META[key];
                  return (
                    <div key={key}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <svg className="w-3.5 h-3.5 text-dark-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={meta?.icon || ''} />
                          </svg>
                          <span className="text-dark-300 text-xs font-medium">{meta?.label || key}</span>
                        </div>
                        <span className="text-dark-500 text-[10px] tabular-nums">{cat.score}/{cat.max}</span>
                      </div>
                      <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <motion.div
                          className="h-full rounded-full bg-primary-500"
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 1.2, delay: 0.3, ease: 'easeOut' }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Tip */}
              {tip && (
                <p className="text-dark-500 text-[11px] mt-4 leading-snug">
                  <span className="text-primary-400">Tip:</span> {tip}
                </p>
              )}
            </div>
          </div>
        </motion.div>

        {showModal && createPortal(
          <BreakdownModal data={data} tierLabel={tierLabel} tierColor={tierColor} onClose={() => setShowModal(false)} />,
          document.body
        )}
      </>
    );
  }

  // ── Non-bento compact card ─────────────────────────────────────

  return (
    <>
      <Card gradient className="cursor-pointer" hover>
        <div onClick={() => setShowModal(true)}>
          <p className="text-dark-400 text-sm mb-3">Co-op Readiness</p>
          <div className="flex items-center gap-4">
            <GlowRing value={data.total} size={80} />
            <div className="text-sm">
              <p className="font-semibold" style={{ color: tierColor }}>{tierLabel}</p>
              <div className="mt-1.5 space-y-1">
                {Object.entries(data.breakdown).map(([key, cat]) => (
                  <div key={key} className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-dark-700 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary-500 transition-all duration-700"
                        style={{ width: `${(cat.score / cat.max) * 100}%` }}
                      />
                    </div>
                    <span className="text-dark-400 text-[10px]">{CATEGORY_META[key]?.label || key}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </Card>

      {showModal && <BreakdownModal data={data} tierLabel={tierLabel} tierColor={tierColor} onClose={() => setShowModal(false)} />}
    </>
  );
}

// ── Breakdown Modal ──────────────────────────────────────────────

function BreakdownModal({ data, tierLabel, tierColor, onClose }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-dark-800 border border-dark-700 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="relative p-6 pb-4">
          <div className="absolute top-0 left-0 right-0 h-1 bg-primary-500" />
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-white">Readiness Breakdown</h3>
            <button onClick={onClose} className="text-dark-400 hover:text-white transition">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="flex items-center gap-4 mt-3">
            <GlowRing value={data.total} size={72} showText={false} />
            <div>
              <p className="text-3xl font-bold text-white">{data.total}%</p>
              <p className="text-sm font-semibold" style={{ color: tierColor }}>{tierLabel}</p>
            </div>
          </div>
        </div>

        {/* Categories */}
        <div className="px-6 pb-6 space-y-4">
          {Object.entries(data.breakdown).map(([key, cat]) => {
            const meta = CATEGORY_META[key];
            const pct = cat.max > 0 ? (cat.score / cat.max) * 100 : 0;
            return (
              <div key={key} className="bg-dark-900/50 border border-dark-700 rounded-xl p-4">
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-8 h-8 rounded-lg bg-dark-700 flex items-center justify-center">
                    <svg className="w-4 h-4 text-dark-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={meta?.icon || ''} />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="text-white text-sm font-medium">{meta?.label || key}</span>
                      <span className="text-sm font-semibold" style={{ color: tierColor }}>
                        {cat.score}/{cat.max}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="h-2 bg-dark-700 rounded-full overflow-hidden mb-2">
                  <motion.div
                    className="h-full rounded-full bg-primary-500"
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.8, ease: 'easeOut' }}
                  />
                </div>
                <p className="text-dark-400 text-xs">{cat.detail}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
