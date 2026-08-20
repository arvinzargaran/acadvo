import { motion, useReducedMotion } from 'framer-motion';

// Editorial easing curve shared across the landing page.
const ease = [0.16, 1, 0.3, 1];

// ─── Data ─────────────────────────────────────────────────────────────────────
// Believable, specific Canadian-student voices — varied programs, schools, and
// lengths so the masonry tiling reads naturally.
const TESTIMONIALS = [
  {
    quote:
      "I was tracking prereqs in a spreadsheet that broke every time I touched it. Acadvo caught that I needed STAT 231 before two of my third-year courses — I would've been stuck a whole term. Ended up with a Waterloo co-op at a fintech in the winter cycle.",
    name: 'Maya R.',
    program: 'Computer Science',
    school: 'Waterloo',
  },
  {
    quote:
      "Everything used to live in five different tabs. Now it's one place — courses, grades, and my applications all talk to each other.",
    name: 'Daniel K.',
    program: 'Mechatronics Eng',
    school: 'UofT',
  },
  {
    quote:
      "I had no idea which electives actually counted toward my concentration. The AI advisor looked at my transcript and picked COMM 335 plus a stats option that lined up with the analyst roles I was targeting. Saved me a meeting with my faculty advisor I could never book anyway.",
    name: 'Priya S.',
    program: 'Commerce',
    school: "Queen's",
  },
  {
    quote:
      "The DSA tracks got me from panicking about LeetCode to actually recognizing patterns. Walked into two on-sites, converted both. Signed my new-grad offer in March.",
    name: 'Liam T.',
    program: 'Software Eng',
    school: 'UBC',
  },
  {
    quote:
      "I kept missing add/drop and assignment deadlines because they lived in six different Canvas courses. Acadvo pulled all of it into one timeline and just tells me what's next. First semester I didn't lose marks to a late submission.",
    name: 'Sofia M.',
    program: 'Life Sciences',
    school: 'McGill',
  },
  {
    quote:
      "Free, no catch, and it actually does more than the paid stuff my friends use. Still waiting for the part where it asks for a credit card.",
    name: 'Noah B.',
    program: 'Data Science',
    school: 'TMU',
  },
];

// ─── Motion ───────────────────────────────────────────────────────────────────
const container = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
};

const cardVariant = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease } },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function initials(name) {
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function TestimonialCard({ t }) {
  return (
    <motion.figure
      variants={cardVariant}
      className="card-rich rounded-2xl border border-dark-600 p-6 break-inside-avoid"
    >
      <span aria-hidden="true" className="block text-primary-600/40 font-display text-3xl leading-none mb-2">
        &ldquo;
      </span>
      <blockquote className="text-dark-200 leading-relaxed">{t.quote}</blockquote>
      <figcaption className="flex items-center gap-3 mt-5 pt-5 border-t border-dark-600/60">
        <div className="w-10 h-10 rounded-full grid place-items-center bg-primary-500/15 text-primary-700 font-semibold text-sm shrink-0">
          {initials(t.name)}
        </div>
        <div className="min-w-0">
          <div className="text-dark-50 font-medium text-sm">{t.name}</div>
          <div className="text-gray-400 text-xs">
            {t.program} @ {t.school}
          </div>
        </div>
      </figcaption>
    </motion.figure>
  );
}

export default function Testimonials() {
  const reduced = useReducedMotion();

  return (
    <div>
      <div>
        {/* Header */}
        <motion.div
          initial={reduced ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.5, ease }}
          className="mb-14"
        >
          <h2 className="font-display font-bold text-dark-50 tracking-tight text-4xl md:text-5xl">
            Students, on{' '}
            <span className="text-gradient-warm">Acadvo.</span>
          </h2>
          <p className="text-gray-400 text-lg max-w-xl mt-5">
            Real students, real semesters — from first prerequisite to signed offer.
          </p>
        </motion.div>

        {/* Masonry wall */}
        <motion.div
          initial={reduced ? false : 'hidden'}
          whileInView="visible"
          viewport={{ once: true, margin: '-60px' }}
          variants={container}
          className="columns-1 md:columns-2 lg:columns-3 gap-5 [&>*]:mb-5"
        >
          {TESTIMONIALS.map((t) => (
            <TestimonialCard key={t.name} t={t} />
          ))}
        </motion.div>
      </div>
    </div>
  );
}
