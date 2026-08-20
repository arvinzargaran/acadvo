import { motion, useReducedMotion } from 'framer-motion';

/* ─────────────────────────────────────────────────────────────────────────────
   First run — the departure board.

   This slot used to hold a wall of testimonials that were written rather than
   collected. Until there are real students to quote, the honest thing to put in
   front of someone deciding whether to sign up is exactly what the next ten
   minutes will ask of them.

   Every figure below is the real step count from `OnboardingPage`'s QUESTIONS
   array — six profile questions, one upload, one review, two optional stages,
   one launch. If that array changes, change these.

   Structurally this is a departure board, which is the one piece of station
   furniture the rest of the page doesn't already use — the hero is a map, the
   summary is a ruled table, the lines section is a zig-zag.
   ────────────────────────────────────────────────────────────────────────── */

const ease = [0.22, 1, 0.36, 1];

const STAGES = [
  {
    stop: '01',
    line: 'c',
    letter: 'C',
    name: 'About you',
    calls: 'School, program, start and graduation year, and what you are working towards.',
    steps: 6,
  },
  {
    stop: '02',
    line: 'c',
    letter: 'C',
    name: 'Your degree',
    calls: 'Upload your program checklist. Acadvo reads the requirements out of it.',
    steps: 1,
  },
  {
    stop: '03',
    line: 'c',
    letter: 'C',
    name: 'Your courses',
    calls: 'Confirm what you have finished and what you are taking now.',
    steps: 1,
  },
  {
    stop: '04',
    line: 'w',
    letter: 'W',
    name: 'Projects and targets',
    calls: 'Portfolio projects and the companies you are aiming at. Both optional.',
    steps: 2,
    optional: true,
  },
  {
    stop: '05',
    line: 'live',
    letter: 'A',
    name: 'Launch',
    calls: 'Prerequisite map, term plan, and the advisor all come up at once.',
    steps: 1,
  },
];

const row = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease } },
};

const board = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.07 } },
};

export default function FirstRun() {
  const reduced = useReducedMotion();

  return (
    <div>
      <motion.div
        initial={reduced ? false : { opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.5, ease }}
        className="mb-12 max-w-2xl"
      >
        <p className="text-lg leading-relaxed" style={{ color: 'var(--wf-muted)' }}>
          Setup is eleven questions and one upload. Nothing is filled in for you,
          and nothing is guessed — everything the planner does afterwards comes
          out of what you enter here.
        </p>
      </motion.div>

      {/* The board. A header rule and hairlines between services, the way a
          printed timetable is set — no cards, no shadows. */}
      <motion.div
        initial={reduced ? false : 'hidden'}
        whileInView="visible"
        viewport={{ once: true, margin: '-60px' }}
        variants={board}
        style={{ borderTop: '2px solid var(--wf-ink)' }}
      >
        <div
          className="hidden md:grid grid-cols-[3.5rem_1fr_2fr_5rem] gap-5 py-3"
          style={{ borderBottom: '1px solid var(--wf-rule)' }}
        >
          {['Stop', 'Service', 'Calls at', 'Steps'].map((h) => (
            <span key={h} className="wf-signage text-[9px]" style={{ color: 'var(--wf-muted)' }}>
              {h}
            </span>
          ))}
        </div>

        {STAGES.map((s) => (
          <motion.div
            key={s.stop}
            variants={row}
            className="grid grid-cols-[2.75rem_1fr] md:grid-cols-[3.5rem_1fr_2fr_5rem] gap-x-5 gap-y-2 py-5 items-baseline"
            style={{ borderBottom: '1px solid var(--wf-rule)' }}
          >
            <span className="wf-code text-sm" style={{ color: 'var(--wf-muted)' }}>
              {s.stop}
            </span>

            <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1 min-w-0">
              <span
                className={`wf-bullet wf-bullet-${s.line}`}
                style={{ width: '1.15rem', height: '1.15rem', fontSize: '0.625rem' }}
                aria-hidden="true"
              >
                {s.letter}
              </span>
              {/* Wraps rather than truncates: "Projects and targets" clipped to
                  "PROJECTS AND TARG…" on a 375px screen. */}
              <span className="wf-signage text-[11px]" style={{ color: 'var(--wf-ink)' }}>
                {s.name}
              </span>
              {s.optional && (
                <span className="wf-signage text-[9px]" style={{ color: 'var(--wf-muted)' }}>
                  Optional
                </span>
              )}
            </span>

            {/* On mobile the description drops under the service name and lines
                up with it rather than with the stop number. */}
            <p
              className="col-start-2 md:col-start-3 text-[0.9375rem] leading-relaxed"
              style={{ color: 'var(--wf-muted)' }}
            >
              {s.calls}
            </p>

            {/* The column header carries the unit on desktop. On mobile the
                header is gone, so a bare "6" under a paragraph means nothing —
                the word comes back. */}
            <span
              className="col-start-2 md:col-start-4 wf-num text-sm md:text-right"
              style={{ color: 'var(--wf-muted)' }}
            >
              {s.steps}
              <span className="md:hidden">{s.steps === 1 ? ' step' : ' steps'}</span>
            </span>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}
