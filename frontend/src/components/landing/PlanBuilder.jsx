import { useMemo, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';

// ─── Motion preset ────────────────────────────────────────────────────────────
const ease = [0.16, 1, 0.3, 1];

// ─── Data ─────────────────────────────────────────────────────────────────────
// Three universities × three programs, each with a plausible 4-semester roadmap
// using believable Canadian-style course codes that vary by school + program.

const UNIVERSITIES = [
  { id: 'waterloo', name: 'University of Waterloo', short: 'Waterloo' },
  { id: 'toronto', name: 'University of Toronto', short: 'U of T' },
  { id: 'ubc', name: 'UBC', short: 'UBC' },
];

const PROGRAMS = [
  { id: 'cs', name: 'Computer Science', short: 'CS' },
  { id: 'mech', name: 'Mechanical Eng.', short: 'Mech Eng' },
  { id: 'commerce', name: 'Commerce', short: 'Commerce' },
];

const GOALS = [
  { id: 'coop', label: 'Co-op / Internship', tail: 'a strong signal on co-op applications.' },
  { id: 'grad', label: 'Grad school', tail: 'the research prerequisite grad programs look for.' },
  { id: 'industry', label: 'Full-time role', tail: 'the depth recruiters screen for full-time.' },
];

const SEM_LABELS = ['Year 1 — Fall', 'Year 1 — Winter', 'Year 2 — Fall', 'Year 2 — Winter'];

// Each roadmap: 4 semesters of 3 course codes, how many are "done", a progress %,
// and an AI pick (a specific next course + why). done = number of completed sems.
const ROADMAPS = {
  waterloo: {
    cs: {
      done: 2,
      progress: 54,
      sems: [
        ['CS 135', 'MATH 135', 'ENGL 109'],
        ['CS 136', 'MATH 137', 'STAT 230'],
        ['CS 245', 'CS 246', 'MATH 239'],
        ['CS 341', 'CS 350', 'STAT 231'],
      ],
      pick: { code: 'CS 240', why: 'unlocks CS 341 & CS 350 — the gateway to your upper-year systems track.' },
    },
    mech: {
      done: 2,
      progress: 51,
      sems: [
        ['ME 100', 'MATH 115', 'PHYS 115'],
        ['ME 101', 'MATH 116', 'CHE 102'],
        ['ME 201', 'ME 219', 'MATH 217'],
        ['ME 230', 'ME 250', 'ME 262'],
      ],
      pick: { code: 'ME 269', why: 'prerequisite for the mechatronics stream and most 4th-year design labs.' },
    },
    commerce: {
      done: 1,
      progress: 42,
      sems: [
        ['AFM 101', 'ECON 101', 'COMM 101'],
        ['AFM 102', 'ECON 102', 'MATH 127'],
        ['AFM 231', 'COMM 231', 'STAT 211'],
        ['AFM 273', 'COMM 301', 'ECON 201'],
      ],
      pick: { code: 'AFM 291', why: 'gates the accounting specialization and the CFE-track courses.' },
    },
  },
  toronto: {
    cs: {
      done: 2,
      progress: 56,
      sems: [
        ['CSC110', 'MAT137', 'ENG100'],
        ['CSC111', 'MAT223', 'STA130'],
        ['CSC207', 'CSC236', 'MAT237'],
        ['CSC258', 'CSC263', 'STA247'],
      ],
      pick: { code: 'CSC209', why: 'the systems prerequisite for CSC369 & CSC343 — needed before internships.' },
    },
    mech: {
      done: 2,
      progress: 50,
      sems: [
        ['MIE100', 'MAT186', 'PHY180'],
        ['MIE191', 'MAT187', 'CIV102'],
        ['MIE231', 'MIE221', 'MAT290'],
        ['MIE262', 'MIE301', 'MIE350'],
      ],
      pick: { code: 'MIE304', why: 'control-systems prerequisite for the robotics and design capstones.' },
    },
    commerce: {
      done: 1,
      progress: 40,
      sems: [
        ['RSM100', 'ECO101', 'MAT133'],
        ['RSM219', 'ECO102', 'STA220'],
        ['RSM222', 'RSM230', 'ECO206'],
        ['RSM250', 'RSM332', 'MGT262'],
      ],
      pick: { code: 'RSM332', why: 'capital-market theory — the gate into the finance specialist stream.' },
    },
  },
  ubc: {
    cs: {
      done: 2,
      progress: 53,
      sems: [
        ['CPSC 110', 'MATH 100', 'WRDS 150'],
        ['CPSC 121', 'MATH 101', 'PHYS 117'],
        ['CPSC 210', 'CPSC 221', 'MATH 200'],
        ['CPSC 213', 'CPSC 310', 'STAT 251'],
      ],
      pick: { code: 'CPSC 320', why: 'algorithm design — required before co-op and most 400-level electives.' },
    },
    mech: {
      done: 2,
      progress: 49,
      sems: [
        ['MECH 220', 'MATH 100', 'PHYS 157'],
        ['MECH 221', 'MATH 101', 'CHEM 154'],
        ['MECH 260', 'MECH 280', 'MATH 255'],
        ['MECH 305', 'MECH 325', 'MECH 360'],
      ],
      pick: { code: 'MECH 375', why: 'heat transfer — prerequisite for thermofluids design and most electives.' },
    },
    commerce: {
      done: 1,
      progress: 41,
      sems: [
        ['COMM 101', 'ECON 101', 'MATH 104'],
        ['COMM 191', 'ECON 102', 'MATH 105'],
        ['COMM 290', 'COMM 293', 'COMM 291'],
        ['COMM 335', 'COMM 370', 'COMM 204'],
      ],
      pick: { code: 'COMM 370', why: 'corporate finance — the gate into the finance and Portfolio Management track.' },
    },
  },
};

// ─── Local primitives ─────────────────────────────────────────────────────────

/** A segmented row of pill buttons — real <button>s, keyboard accessible. */
function PillGroup({ legend, options, value, onChange }) {
  return (
    <fieldset className="min-w-0">
      <legend className="text-[10px] tracking-[0.22em] uppercase text-dark-400 mb-2">{legend}</legend>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label={legend}>
        {options.map((opt) => {
          const active = opt.id === value;
          return (
            <button
              key={opt.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(opt.id)}
              className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
                active
                  ? 'bg-primary-500/15 border-primary-500/30 text-primary-700'
                  : 'bg-dark-900/40 border-dark-600 text-dark-300 hover:bg-dark-700 hover:text-dark-50'
              }`}
            >
              {opt.short || opt.name}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function PlanBuilder() {
  const reduced = useReducedMotion();

  const [uni, setUni] = useState(UNIVERSITIES[0].id);
  const [program, setProgram] = useState(PROGRAMS[0].id);
  const [goal, setGoal] = useState(GOALS[0].id);

  const roadmap = ROADMAPS[uni][program];
  const goalMeta = useMemo(() => GOALS.find((g) => g.id === goal), [goal]);
  const uniMeta = useMemo(() => UNIVERSITIES.find((u) => u.id === uni), [uni]);
  const programMeta = useMemo(() => PROGRAMS.find((p) => p.id === program), [program]);

  // Changing this key remounts the results block, so the stagger replays on
  // every selection change. Goal is included so the AI line re-animates too.
  const selectionKey = `${uni}-${program}-${goal}`;

  const container = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.045, delayChildren: 0.05 } },
  };
  const item = {
    hidden: { opacity: 0, y: 8 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease } },
  };

  const recommendation = `${roadmap.pick.code} — ${roadmap.pick.why} It's ${goalMeta.tail}`;

  return (
    // The heading and standfirst live in the page's station sign, so this
    // component is only the panel.
    <div>
      <div>
        {/* ── Product panel ── */}
        <div className="border border-dark-600 card-rich shadow-editorial overflow-hidden">
          {/* Control row */}
          <div className="border-b border-dark-600/70 bg-dark-900/40 p-5 md:p-6">
            <div className="flex flex-col md:flex-row md:items-start gap-6 md:gap-10">
              <PillGroup legend="University" options={UNIVERSITIES} value={uni} onChange={setUni} />
              <PillGroup legend="Program" options={PROGRAMS} value={program} onChange={setProgram} />
              <PillGroup legend="Career goal" options={GOALS.map((g) => ({ id: g.id, short: g.label }))} value={goal} onChange={setGoal} />
            </div>
          </div>

          {/* Results */}
          <div className="p-5 md:p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="text-xs text-dark-400">
                <span className="text-dark-200 font-medium">{uniMeta.name}</span>
                <span className="mx-1.5 text-dark-500">/</span>
                <span className="text-dark-200 font-medium">{programMeta.name}</span>
              </div>
              <span className="text-[10px] tracking-[0.22em] uppercase text-dark-400 hidden sm:block">
                acadvo — degree planner
              </span>
            </div>

            {/* Semester cards — re-key to replay the stagger on selection change */}
            <AnimatePresence mode="wait">
              <motion.div
                key={selectionKey}
                variants={reduced ? undefined : container}
                initial={reduced ? false : 'hidden'}
                animate="visible"
                className="grid grid-cols-1 sm:grid-cols-2 gap-3"
              >
                {roadmap.sems.map((courses, si) => {
                  const done = si < roadmap.done;
                  return (
                    <motion.div
                      key={SEM_LABELS[si]}
                      variants={reduced ? undefined : item}
                      className={`rounded-xl border p-3.5 ${
                        done ? 'border-emerald-500/25 bg-emerald-500/5' : 'border-dark-600 bg-dark-900/30'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2.5">
                        <span className={`text-xs font-semibold ${done ? 'text-emerald-600' : 'text-dark-400'}`}>
                          {SEM_LABELS[si]}
                        </span>
                        <span
                          className={`text-[10px] tracking-[0.16em] uppercase ${
                            done ? 'text-emerald-600' : 'text-dark-400'
                          }`}
                        >
                          {done ? 'Done' : 'Planned'}
                        </span>
                      </div>
                      <motion.div
                        variants={reduced ? undefined : container}
                        className="flex flex-col gap-1.5"
                      >
                        {courses.map((code) => (
                          <motion.div
                            key={code}
                            variants={reduced ? undefined : item}
                            className="flex items-center gap-2"
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                done ? 'bg-emerald-500' : 'bg-dark-500'
                              }`}
                            />
                            <span className="text-sm text-dark-200 font-medium tabular-nums">{code}</span>
                          </motion.div>
                        ))}
                      </motion.div>
                    </motion.div>
                  );
                })}
              </motion.div>
            </AnimatePresence>

            {/* Degree progress */}
            <div className="mt-4 rounded-xl border border-dark-600 bg-dark-900/30 p-3.5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-dark-400">Degree progress</span>
                <span className="text-xs text-dark-200 font-semibold tabular-nums">{roadmap.progress}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-dark-700 overflow-hidden">
                <motion.div
                  key={`${selectionKey}-bar`}
                  className="h-full rounded-full bg-primary-500"
                  initial={reduced ? false : { width: 0 }}
                  animate={{ width: `${roadmap.progress}%` }}
                  transition={{ duration: reduced ? 0 : 0.7, ease, delay: reduced ? 0 : 0.25 }}
                />
              </div>
            </div>

            {/* AI pick callout (amber) */}
            <AnimatePresence mode="wait">
              <motion.div
                key={`${selectionKey}-ai`}
                initial={reduced ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? undefined : { opacity: 0 }}
                transition={{ duration: reduced ? 0 : 0.4, ease, delay: reduced ? 0 : 0.35 }}
                className="mt-3 rounded-xl border icon-chip p-3.5 flex items-start gap-3"
              >
                <span className="mt-0.5 flex-shrink-0 flex items-center gap-1.5 rounded-full bg-primary-500/20 border border-primary-500/30 px-2 py-0.5 text-[10px] font-semibold tracking-[0.12em] uppercase text-primary-700">
                  <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
                    <path d="M10 2.5l1.6 4.9h5.1l-4.1 3 1.6 4.9L10 12.3l-4.2 3 1.6-4.9-4.1-3h5.1z" />
                  </svg>
                  AI pick
                </span>
                <p className="text-sm text-dark-200 leading-relaxed">
                  <span className="font-semibold text-dark-50">{roadmap.pick.code}</span> next —{' '}
                  <span className="text-dark-300">{recommendation.replace(`${roadmap.pick.code} — `, '')}</span>
                </p>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
