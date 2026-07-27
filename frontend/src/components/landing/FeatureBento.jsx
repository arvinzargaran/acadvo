import { useRef } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

// ─── Motion presets ───────────────────────────────────────────────────────────
const ease = [0.16, 1, 0.3, 1];

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
};

const tileVariant = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease } },
};

// ─── Icons (heroicons-style stroke) ───────────────────────────────────────────
const iconProps = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  className: 'w-6 h-6',
};

const DegreeIcon = (
  <svg {...iconProps}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5" />
  </svg>
);

const GpaIcon = (
  <svg {...iconProps}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
  </svg>
);

const PipelineIcon = (
  <svg {...iconProps}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0M12 12.75h.008v.008H12v-.008z" />
  </svg>
);

const AdvisorIcon = (
  <svg {...iconProps}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
  </svg>
);

const DsaIcon = (
  <svg {...iconProps}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z" />
  </svg>
);

const ProjectIcon = (
  <svg {...iconProps}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
  </svg>
);

// ─── Feature data ─────────────────────────────────────────────────────────────
// `span` is the lg 12-col placement; auto-flow tiles the rest cleanly around
// the hero. Order matters for the flow, so keep it.
const FEATURES = [
  {
    icon: AdvisorIcon,
    title: 'AI Course Advisor',
    description:
      'Personalized course picks based on your career target, GPA, and degree requirements — an advisor that actually knows your situation.',
    hero: true,
    span: 'lg:col-span-6 lg:row-span-2 md:col-span-2',
  },
  {
    icon: DegreeIcon,
    title: 'Degree Planner',
    description: 'Map every course, satisfy prerequisites, and graduate on schedule with zero surprises.',
    span: 'lg:col-span-6',
  },
  {
    icon: GpaIcon,
    title: 'GPA Tracker',
    description: 'Monitor grades in real time and simulate scenarios to protect your average before it drops.',
    span: 'lg:col-span-3',
  },
  {
    icon: PipelineIcon,
    title: 'Co-op / Internship Pipeline',
    description: 'Track every application, interview, and offer in one place. Know exactly where you stand.',
    span: 'lg:col-span-3',
  },
  {
    icon: DsaIcon,
    title: 'DSA Interview Prep',
    description: 'Structured practice tracks and pattern guides to ace technical and behavioral interviews.',
    span: 'lg:col-span-5',
  },
  {
    icon: ProjectIcon,
    title: 'Project Tracker',
    description: 'Keep portfolio projects moving with milestones, deadlines, and progress you can show recruiters.',
    span: 'lg:col-span-7',
  },
];

// ─── Bento tile w/ cursor-tracking amber glow ─────────────────────────────────
function BentoTile({ feature }) {
  const ref = useRef(null);
  const reduced = useReducedMotion();
  const { hero } = feature;

  function onMouseMove(e) {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty('--mx', `${e.clientX - rect.left}px`);
    el.style.setProperty('--my', `${e.clientY - rect.top}px`);
  }

  return (
    <motion.div
      ref={ref}
      variants={tileVariant}
      onMouseMove={reduced ? undefined : onMouseMove}
      className={`group card-rich rounded-2xl border border-dark-600 overflow-hidden transition-[box-shadow,border-color] duration-300 hover:shadow-editorial hover:border-primary-500/40 ${
        hero ? 'p-8 flex flex-col' : 'p-6'
      } ${feature.span}`}
    >
      {/* Cursor-tracking amber highlight (disabled under reduced motion) */}
      {!reduced && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover:opacity-100"
          style={{
            background:
              'radial-gradient(220px circle at var(--mx, 50%) var(--my, 50%), rgba(255,138,0,0.15), transparent 60%)',
          }}
        />
      )}

      <div className={`relative ${hero ? 'flex flex-col h-full' : ''}`}>
        <div
          className={`icon-chip inline-flex items-center justify-center rounded-xl text-primary-700 ${
            hero ? 'w-14 h-14 mb-6' : 'w-12 h-12 mb-5'
          }`}
        >
          {feature.icon}
        </div>

        {hero && (
          <span className="text-[11px] tracking-[0.28em] uppercase text-primary-600 mb-3">
            Flagship
          </span>
        )}

        <h3
          className={`font-semibold text-dark-50 ${
            hero ? 'font-display text-2xl md:text-3xl mb-3 tracking-tight' : 'text-lg mb-2'
          }`}
        >
          {feature.title}
        </h3>
        <p
          className={`text-gray-400 leading-relaxed ${
            hero ? 'text-base max-w-md' : 'text-sm'
          }`}
        >
          {feature.description}
        </p>
      </div>
    </motion.div>
  );
}

// ─── Section ──────────────────────────────────────────────────────────────────
export default function FeatureBento() {
  return (
    <section id="features" className="py-28 md:py-32 px-6">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.45, ease }}
          className="mb-14"
        >
          {/* Eyebrow */}
          <div className="flex items-center gap-4 mb-10">
            <span className="font-display text-primary-600 text-base">03</span>
            <span className="text-[11px] tracking-[0.28em] uppercase text-gray-400 whitespace-nowrap">
              The toolkit
            </span>
            <div className="h-px flex-1 bg-dark-600/70" />
          </div>

          <h2 className="font-display font-bold text-dark-50 tracking-tight leading-[0.9] text-[clamp(3rem,9vw,6rem)]">
            Toolkit<span className="text-primary-600">.</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-xl mt-6">
            Stop juggling spreadsheets, Notion pages, and LinkedIn tabs. Acadvo brings your entire
            academic journey into focus.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-60px' }}
          variants={stagger}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 lg:auto-rows-[minmax(11rem,1fr)] gap-4"
        >
          {FEATURES.map((feature) => (
            <BentoTile key={feature.title} feature={feature} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
