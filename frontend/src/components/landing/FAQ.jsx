import { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

const ease = [0.16, 1, 0.3, 1];

// ─── Content ──────────────────────────────────────────────────────────────────
const FAQS = [
  {
    q: 'Is Acadvo really free?',
    a: 'Yes. Every feature, forever. No credit card, no trial timer, no premium tier we upsell you into.',
  },
  {
    q: 'Which universities are supported?',
    a: "25+ Canadian universities including Waterloo, UofT, UBC, McGill, Western, Queen's, and TMU — and the planner works for any program at any school.",
  },
  {
    q: 'Will it work for my specific program?',
    a: 'Yes. You set your university, program, and requirements, and the degree planner adapts to your exact path — including electives and prerequisites.',
  },
  {
    q: 'How does the AI advisor actually know my situation?',
    a: 'It reads your degree progress, grades, and career goal to recommend courses, catch missing prerequisites, and flag graduation gaps — tailored to you, not generic advice.',
  },
  {
    q: 'Is my academic data private?',
    a: "Your data is yours. We don't sell it or share it; it's only used to power your planning and advice.",
  },
  {
    q: 'Do I need to import my transcript to start?',
    a: 'No. You can build a plan from scratch in a few minutes. Importing is optional and just speeds up setup.',
  },
  {
    q: 'Can it help me prep for interviews?',
    a: 'Yes. Structured DSA practice tracks and pattern guides cover both technical and behavioral rounds so you walk in ready.',
  },
];

// ─── Row ──────────────────────────────────────────────────────────────────────
function FaqItem({ item, index, isOpen, onToggle }) {
  const reduced = useReducedMotion();
  const panelId = `faq-panel-${index}`;
  const buttonId = `faq-button-${index}`;

  return (
    <div className="border-b border-dark-600/60">
      <h3>
        <button
          id={buttonId}
          type="button"
          aria-expanded={isOpen}
          aria-controls={panelId}
          onClick={onToggle}
          className="group w-full text-left py-5 flex items-center justify-between gap-4"
        >
          <span className="text-dark-50 font-medium text-lg md:text-xl">{item.q}</span>
          <motion.span
            aria-hidden="true"
            animate={{ rotate: isOpen ? 135 : 0 }}
            transition={{ duration: 0.3, ease }}
            className={`flex-shrink-0 ${isOpen ? 'text-primary-600' : 'text-dark-400 group-hover:text-primary-600'} transition-colors`}
          >
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-5 h-5">
              <path strokeLinecap="round" d="M10 4.5v11M4.5 10h11" />
            </svg>
          </motion.span>
        </button>
      </h3>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            id={panelId}
            role="region"
            aria-labelledby={buttonId}
            key="content"
            initial={reduced ? { opacity: 1 } : { height: 0, opacity: 0 }}
            animate={reduced ? { opacity: 1 } : { height: 'auto', opacity: 1 }}
            exit={reduced ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={reduced ? { duration: 0 } : { duration: 0.3, ease }}
            className="overflow-hidden"
          >
            <p className="text-gray-400 leading-relaxed pb-5 pr-8">{item.a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Section ──────────────────────────────────────────────────────────────────
export default function FAQ() {
  const [openIndex, setOpenIndex] = useState(null);

  return (
    <section id="faq" className="py-28 md:py-32 px-6">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-4 mb-10">
          <span className="font-display text-primary-600 text-base">08</span>
          <span className="text-[11px] tracking-[0.28em] uppercase text-gray-400 whitespace-nowrap">Questions</span>
          <div className="h-px flex-1 bg-dark-600/70" />
        </div>

        <h2 className="font-display font-bold text-dark-50 tracking-tight text-4xl md:text-5xl mb-12">
          Frequently{' '}
          <span className="text-gradient-warm">asked.</span>
        </h2>

        <div className="border-t border-dark-600/60">
          {FAQS.map((item, i) => (
            <FaqItem
              key={item.q}
              item={item}
              index={i}
              isOpen={openIndex === i}
              onToggle={() => setOpenIndex((prev) => (prev === i ? null : i))}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
