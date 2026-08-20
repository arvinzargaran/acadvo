import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { motion, useInView, useMotionValueEvent, useReducedMotion, useScroll, animate } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import LiveAIMock from '../components/landing/LiveAIMock';
import PrereqGraph from '../components/landing/PrereqGraph';
import ComparisonStrip from '../components/landing/ComparisonStrip';
import FirstRun from '../components/landing/FirstRun';
import FAQ from '../components/landing/FAQ';
import PlanBuilder from '../components/landing/PlanBuilder';
import ThemeToggle from '../components/landing/ThemeToggle';
import RouteMap from '../components/landing/wayfinding/RouteMap';
import StationSign from '../components/landing/wayfinding/StationSign';
import LineRail from '../components/landing/wayfinding/LineRail';

/* ─────────────────────────────────────────────────────────────────────────────
   Wayfinding — the landing page.

   The design system lives in index.css under `.wayfinding`. The premise: a
   degree really is a network, so the page is built out of the vocabulary of one
   — line bullets that carry a letter as well as a colour, station signs for
   section headers, octolinear track, and a route diagram down the left margin
   that doubles as the scroll position. Saturated colour appears only inside map
   objects and bullets; every other surface is strict neutral.
   ────────────────────────────────────────────────────────────────────────── */

const ease = [0.22, 1, 0.36, 1];

const rise = {
  hidden: { opacity: 0, y: 18 },
  visible: (delay = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay, ease },
  }),
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
};

/** Standard section shell: consistent measure and vertical rhythm. */
function Section({ id, children, className = '', wide = false }) {
  return (
    <section id={id} className={`px-6 py-24 md:py-32 ${className}`}>
      <div className={`${wide ? 'max-w-6xl' : 'max-w-4xl'} mx-auto`}>{children}</div>
    </section>
  );
}

/** Animated integer that counts up when scrolled into view. */
function Ticker({ value, prefix = '', suffix = '' }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(reduced ? value : 0);

  useEffect(() => {
    if (!inView || reduced) return undefined;
    const controls = animate(0, value, {
      duration: 1.2,
      ease,
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    return () => controls.stop();
  }, [inView, reduced, value]);

  return (
    <span ref={ref} className="wf-num">
      {prefix}
      {display}
      {suffix}
    </span>
  );
}

// ─── Chrome ───────────────────────────────────────────────────────────────────

function Navbar({ user }) {
  const [scrolled, setScrolled] = useState(false);
  const { scrollY } = useScroll();
  useMotionValueEvent(scrollY, 'change', (v) => setScrolled(v > 24));

  return (
    <header
      className="fixed top-0 inset-x-0 z-50 transition-[background-color,border-color,padding] duration-300"
      style={{
        background: scrolled ? 'var(--wf-canvas)' : 'transparent',
        borderBottom: `2px solid ${scrolled ? 'var(--wf-ink)' : 'transparent'}`,
      }}
    >
      <div
        className={`max-w-6xl mx-auto px-6 flex items-center justify-between transition-all duration-300 ${
          scrolled ? 'py-3' : 'py-5'
        }`}
      >
        <a href="#top" className="flex items-center gap-2.5">
          <span className="wf-bullet wf-bullet-live" aria-hidden="true">A</span>
          <span className="wf-signage text-lg" style={{ color: 'var(--wf-ink)' }}>
            acadvo
          </span>
        </a>

        <nav className="hidden md:flex items-center gap-8">
          {[
            ['Lines', '#lines'],
            ['Compare', '#compare'],
            ['Pricing', '#pricing'],
          ].map(([label, href]) => (
            <a
              key={href}
              href={href}
              className="wf-signage text-[11px] transition-opacity hover:opacity-60"
              style={{ color: 'var(--wf-ink)' }}
            >
              {label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <ThemeToggle />
          {user ? (
            <Link
              to="/dashboard"
              className="wf-signage text-[11px] px-4 py-2.5"
              style={{ background: 'var(--wf-ink)', color: 'var(--wf-canvas)' }}
            >
              Dashboard
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="hidden sm:block wf-signage text-[11px] px-2"
                style={{ color: 'var(--wf-muted)' }}
              >
                Sign in
              </Link>
              <Link
                to="/register"
                className="wf-signage text-[11px] px-4 py-2.5"
                style={{ background: 'var(--wf-ink)', color: 'var(--wf-canvas)' }}
              >
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

/** Primary action — a solid signage plate rather than a pill. */
function PlateLink({ to, children, tone = 'ink', className = '' }) {
  const tones = {
    ink: { background: 'var(--wf-ink)', color: 'var(--wf-canvas)', border: '2px solid var(--wf-ink)' },
    outline: { background: 'transparent', color: 'var(--wf-ink)', border: '2px solid var(--wf-ink)' },
  };
  return (
    <Link
      to={to}
      className={`wf-signage inline-flex items-center gap-2.5 px-7 py-4 text-xs transition-transform duration-200 hover:-translate-y-0.5 ${className}`}
      style={tones[tone]}
    >
      {children}
    </Link>
  );
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function Hero({ user }) {
  return (
    <section id="top" className="relative pt-36 md:pt-44 pb-20 px-6 overflow-hidden">
      <div className="max-w-6xl mx-auto">
        {/* Route header: the three lines this network runs. */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, ease }}
          className="flex flex-wrap items-center gap-x-5 gap-y-2 mb-9"
        >
          {[
            ['C', 'wf-bullet-c', 'Degree'],
            ['W', 'wf-bullet-w', 'Co-op'],
            ['A', 'wf-bullet-live', 'Advisor'],
          ].map(([letter, cls, label]) => (
            <span key={letter} className="flex items-center gap-2">
              <span className={`wf-bullet ${cls}`} style={{ width: '1.25rem', height: '1.25rem', fontSize: '0.6875rem' }} aria-hidden="true">
                {letter}
              </span>
              <span className="wf-signage text-[10px]" style={{ color: 'var(--wf-muted)' }}>
                {label}
              </span>
            </span>
          ))}
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.05, ease }}
          className="wf-display text-4xl sm:text-6xl lg:text-7xl max-w-4xl text-balance"
          style={{ color: 'var(--wf-ink)' }}
        >
          Your degree is a network.
          <br />
          <span style={{ color: 'var(--wf-line-c-text)' }}>Here is the map.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15, ease }}
          className="mt-7 text-lg md:text-xl max-w-2xl leading-relaxed"
          style={{ color: 'var(--wf-muted)' }}
        >
          Acadvo reads your program&apos;s real prerequisites, finds the chain that decides
          your graduation date, and plans every term around it — alongside your co-op
          applications and interview prep.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.25, ease }}
          className="mt-10 flex flex-wrap items-center gap-4"
        >
          {user ? (
            <PlateLink to="/dashboard">Open dashboard</PlateLink>
          ) : (
            <>
              <PlateLink to="/register">Plan my degree</PlateLink>
              <PlateLink to="/login" tone="outline">Sign in</PlateLink>
            </>
          )}
          <span className="wf-signage text-[10px]" style={{ color: 'var(--wf-muted)' }}>
            Free · no card
          </span>
        </motion.div>
      </div>

      {/* The map itself — the thesis, drawn from the real prerequisite graph. */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.35, ease }}
        className="max-w-6xl mx-auto mt-12 md:mt-14"
      >
        <RouteMap />
      </motion.div>
    </section>
  );
}

// ─── Where students get stuck ─────────────────────────────────────────────────

const DISRUPTIONS = [
  {
    title: 'Requirements live in a stale spreadsheet',
    body: 'You rebuild it every September and it is wrong by October.',
  },
  {
    title: 'Five apps, none of which talk',
    body: 'Deadlines here, grades there, applications in a third place.',
  },
  {
    title: 'A prerequisite you did not see coming',
    body: 'One missed course closes four others and adds a term.',
  },
  {
    title: 'No idea where you stand',
    body: 'By the time the gap is obvious, it is too late to close it cheaply.',
  },
];

function StuckSection() {
  return (
    <Section id="stuck">
      <StationSign
        name="Where students get stuck"
        note="You are not disorganised. Your tools are."
        className="mb-12"
      />
      <motion.ul
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: '-60px' }}
        variants={stagger}
        className="grid sm:grid-cols-2 gap-px"
        style={{ background: 'var(--wf-rule)' }}
      >
        {DISRUPTIONS.map((d) => (
          <motion.li
            key={d.title}
            variants={rise}
            className="p-6 sm:p-7"
            style={{ background: 'var(--wf-canvas)' }}
          >
            {/* A service-disruption bar: the one place red appears outside a map. */}
            <span
              aria-hidden="true"
              className="block w-9 h-1 mb-4"
              style={{ background: 'var(--wf-line-c)' }}
            />
            <h3 className="wf-signage text-[11px] mb-2" style={{ color: 'var(--wf-ink)' }}>
              {d.title}
            </h3>
            <p className="text-[0.9375rem] leading-relaxed" style={{ color: 'var(--wf-muted)' }}>
              {d.body}
            </p>
          </motion.li>
        ))}
      </motion.ul>
    </Section>
  );
}

// ─── Manifesto ────────────────────────────────────────────────────────────────

function Manifesto() {
  return (
    <section
      className="px-6 py-28 md:py-40"
      style={{ background: 'var(--wf-ink)', color: 'var(--wf-canvas)' }}
    >
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.7, ease }}
        className="max-w-4xl mx-auto"
      >
        <p className="wf-display text-[1.75rem] sm:text-4xl lg:text-[2.75rem] leading-[1.18] text-balance">
          University hands you a course catalogue. Nobody hands you a route.
          Acadvo turns four scattered years into one line you can actually follow
          — courses, applications, and prep all pointing at the same stop.
        </p>
        <div className="mt-10 flex items-center gap-3">
          <span className="wf-bullet wf-bullet-c" aria-hidden="true">C</span>
          <span className="wf-signage text-[10px]" style={{ opacity: 0.65 }}>
            Terminus — graduation, on time
          </span>
        </div>
      </motion.div>
    </section>
  );
}

// ─── Service summary ──────────────────────────────────────────────────────────

// Every figure here is checked against the code, not rounded up for effect:
//   24 — universities selectable in `data/universities.js`
//   16 — universities with a real grading scale in `data/gradingScales.js`
//   12 — patterns in `DSAPrepPage`'s PATTERNS
// If a number changes in the source, change it here too. An unverifiable stat
// on a landing page is the fastest way to make a real product look invented.
const SUMMARY = [
  { label: 'Canadian universities', value: <Ticker value={24} /> },
  { label: 'Grading scales built in', value: <Ticker value={16} /> },
  { label: 'Interview prep patterns', value: <Ticker value={12} /> },
  { label: 'Fare, forever', value: '$0', accent: true },
];

function ServiceSummary() {
  return (
    <Section id="summary">
      <StationSign name="Service summary" className="mb-12" />
      <div style={{ borderTop: '2px solid var(--wf-ink)' }}>
        {SUMMARY.map((row) => (
          <div
            key={row.label}
            className="flex items-baseline justify-between gap-6 py-6"
            style={{ borderBottom: '1px solid var(--wf-rule)' }}
          >
            <span className="wf-signage text-[11px]" style={{ color: 'var(--wf-muted)' }}>
              {row.label}
            </span>
            <span
              className="wf-display text-3xl sm:text-4xl"
              style={{ color: row.accent ? 'var(--wf-line-w-text)' : 'var(--wf-ink)' }}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </Section>
  );
}

// ─── Lines (the product areas) ────────────────────────────────────────────────

function CoopPipelineMock() {
  const stages = [
    { label: 'Applied', items: ['Shopify — SWE Intern', 'RBC Ventures — Analyst'] },
    { label: 'Interview', items: ['Wealthsimple — Co-op'] },
    { label: 'Offer', items: ['TD Lab — Developer'], live: true },
  ];
  return (
    <div className="wf-raised">
      <div
        className="flex items-center gap-2.5 px-4 py-3"
        style={{ borderBottom: '1px solid var(--wf-rule)' }}
      >
        <span className="wf-bullet wf-bullet-w" style={{ width: '1.1rem', height: '1.1rem', fontSize: '0.625rem' }} aria-hidden="true">W</span>
        <span className="wf-signage text-[10px]" style={{ color: 'var(--wf-muted)' }}>
          Co-op pipeline
        </span>
      </div>
      <div className="p-4 grid grid-cols-3 gap-3">
        {stages.map((stage) => (
          <div key={stage.label}>
            <div
              className="wf-signage text-[9px] pb-2 mb-2.5"
              style={{
                color: stage.live ? 'var(--wf-line-w-text)' : 'var(--wf-muted)',
                borderBottom: `2px solid ${stage.live ? 'var(--wf-line-w)' : 'var(--wf-rule)'}`,
              }}
            >
              {stage.label}
            </div>
            <div className="flex flex-col gap-2">
              {stage.items.map((item) => (
                <div key={item} className="wf-sunk p-2.5">
                  <p className="text-[11px] leading-snug" style={{ color: 'var(--wf-ink)' }}>
                    {item}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const LINES_CONTENT = [
  {
    line: 'C',
    name: 'Degree planning',
    headline: 'Never miss a prerequisite again.',
    body: 'Every requirement mapped, everything you have finished tracked, and the chain that sets your graduation date marked in red.',
    points: ['Prerequisite map built from your real catalogue', 'Automatic progress against your program', 'Works for any program at any university'],
    Mock: PrereqGraph,
  },
  {
    line: 'W',
    name: 'Co-op and internships',
    headline: 'Your job search, on one board.',
    body: 'Track every application from first click to offer letter, and know exactly where you stand at every company.',
    points: ['Pipeline from applied through to offer', 'Deadline and follow-up reminders', 'Internships, co-ops, and full-time in one place'],
    Mock: CoopPipelineMock,
  },
  {
    line: 'A',
    name: 'The advisor',
    headline: 'An advisor that knows your situation.',
    body: 'Ask anything. Answers come from your degree, your progress, and your goals — not a generic pamphlet.',
    points: ['Course recommendations tied to your goals', 'Graduation-gap and prerequisite detection', 'Career-aware suggestions'],
    Mock: LiveAIMock,
  },
];

function LinesSection() {
  return (
    <Section id="lines" wide>
      <StationSign
        name="Three lines, one network"
        note="Each runs on its own, and they interchange where it matters."
        className="mb-16"
      />
      <div className="flex flex-col gap-24 md:gap-32">
        {LINES_CONTENT.map((l, i) => (
          <motion.div
            key={l.line}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-80px' }}
            variants={stagger}
            className={`grid lg:grid-cols-2 gap-10 lg:gap-14 items-center ${
              i % 2 === 1 ? 'lg:[&>*:first-child]:order-2' : ''
            }`}
          >
            {/* min-w-0: a grid item defaults to min-width:auto, so the wide
                diagram in the mock column would otherwise force both tracks
                past the viewport instead of letting the mock scroll inside
                its own container. */}
            <motion.div variants={rise} className="min-w-0">
              <div className="flex items-center gap-3 mb-5">
                <span className={`wf-bullet wf-bullet-${l.line === 'A' ? 'live' : l.line.toLowerCase()}`} aria-hidden="true">
                  {l.line}
                </span>
                <span className="wf-signage text-[11px]" style={{ color: 'var(--wf-muted)' }}>
                  {l.name}
                </span>
              </div>
              <h3 className="wf-display text-3xl md:text-4xl mb-4" style={{ color: 'var(--wf-ink)' }}>
                {l.headline}
              </h3>
              <p className="text-lg leading-relaxed mb-7" style={{ color: 'var(--wf-muted)' }}>
                {l.body}
              </p>
              <ul className="flex flex-col">
                {l.points.map((p) => (
                  <li
                    key={p}
                    className="flex items-start gap-3.5 py-3 text-[0.9375rem]"
                    style={{ borderTop: '1px solid var(--wf-rule)', color: 'var(--wf-ink)' }}
                  >
                    <span
                      aria-hidden="true"
                      className="mt-[0.4rem] flex-shrink-0 rounded-full"
                      style={{
                        width: 8,
                        height: 8,
                        background: 'var(--wf-canvas)',
                        boxShadow: '0 0 0 2.5px var(--wf-muted)',
                      }}
                    />
                    {p}
                  </li>
                ))}
              </ul>
            </motion.div>
            <motion.div variants={rise} className="min-w-0">
              <l.Mock />
            </motion.div>
          </motion.div>
        ))}
      </div>
    </Section>
  );
}

// ─── Networks served ──────────────────────────────────────────────────────────

// Only schools with a real grading scale in `data/gradingScales.js` appear here.
// A logo wall on a landing page reads as endorsement, so the bar for putting a
// university's mark on it is that Acadvo genuinely knows how that school grades
// — not that we would like it to. (Dalhousie was listed here with no scale
// behind it; it comes back the day one lands.)
const UNIVERSITIES = [
  { name: 'University of Toronto',   logo: '/logos/uoft.svg',      invert: true },
  { name: 'UBC',                     logo: '/logos/ubc.svg',       invert: true },
  { name: 'McGill University',       logo: '/logos/mcgill.png' },
  { name: 'Western University',      logo: '/logos/western.svg' },
  { name: 'York University',         logo: '/logos/york.png',      invert: true },
  { name: 'Toronto Metropolitan',    logo: '/logos/tmu.svg' },
  { name: "Queen's University",      logo: '/logos/queens.svg' },
  { name: 'University of Waterloo',  logo: '/logos/waterloo.svg',  invert: true },
  { name: 'McMaster University',     logo: '/logos/mcmaster.png' },
  { name: 'University of Ottawa',    logo: '/logos/ottawa.svg',    invert: true },
  { name: 'Carleton University',     logo: '/logos/carleton.svg',  invert: true },
  { name: 'Concordia University',    logo: '/logos/concordia.svg', invert: true },
  { name: 'Simon Fraser University', logo: '/logos/sfu.png' },
  { name: 'University of Calgary',   logo: '/logos/ucalgary.svg' },
];

function NetworksServed() {
  const doubled = [...UNIVERSITIES, ...UNIVERSITIES];
  return (
    <section
      className="py-14"
      style={{ borderTop: '1px solid var(--wf-rule)', borderBottom: '1px solid var(--wf-rule)' }}
    >
      <p
        className="wf-signage text-[10px] text-center mb-8"
        style={{ color: 'var(--wf-muted)' }}
      >
        Grading scales built in
      </p>
      <div className="marquee-viewport relative h-12 overflow-hidden">
        <div className="absolute flex w-max items-center h-full marquee-left" style={{ '--marquee-duration': '60s' }}>
          {doubled.map((uni, i) => (
            <div key={i} className="flex-shrink-0 mx-9 h-9 w-[128px] flex items-center justify-center">
              <img
                src={uni.logo}
                alt={uni.name}
                /* Desaturated so fifteen brand palettes can't undo the page's
                   one rule: saturated colour belongs to the lines. Full colour
                   returns on hover. */
                className={`h-full w-full object-contain grayscale opacity-50 transition-[filter,opacity] duration-300 hover:grayscale-0 hover:opacity-100 ${
                  uni.invert ? 'logo-dark-invert' : ''
                }`}
              />
            </div>
          ))}
        </div>
        <div className="pointer-events-none absolute inset-y-0 left-0 w-28 z-10" style={{ background: 'linear-gradient(to right, var(--wf-canvas), transparent)' }} />
        <div className="pointer-events-none absolute inset-y-0 right-0 w-28 z-10" style={{ background: 'linear-gradient(to left, var(--wf-canvas), transparent)' }} />
      </div>
    </section>
  );
}

// ─── Pricing ──────────────────────────────────────────────────────────────────

const PERKS = [
  'Degree planner for any program',
  'GPA tracker and grade simulator',
  'Co-op and internship pipeline',
  'AI course advisor',
  'Interview prep tracks',
  'Project and milestone tracker',
  'Works at any university',
  'No credit card required',
];

function Pricing() {
  const { user } = useAuth();
  return (
    <Section id="pricing">
      <StationSign
        name="Pricing"
        note="You are already paying enough tuition."
        className="mb-12"
      />
      {/* A single ticket — the fare plate is the only object on the page that
          borrows the ink block, so the price reads as the headline it is. */}
      <div className="wf-raised-strong max-w-xl">
        <div className="px-7 py-8" style={{ background: 'var(--wf-ink)', color: 'var(--wf-canvas)' }}>
          <div className="wf-signage text-[10px] mb-3" style={{ opacity: 0.7 }}>
            Single fare · all lines
          </div>
          <div className="flex items-end gap-3">
            <span className="wf-display text-6xl">$0</span>
            <span className="wf-signage text-[11px] mb-2.5" style={{ opacity: 0.7 }}>
              forever
            </span>
          </div>
        </div>
        <div className="px-7 py-7">
          <ul className="flex flex-col mb-7">
            {PERKS.map((perk) => (
              <li
                key={perk}
                className="flex items-center gap-3.5 py-2.5 text-[0.9375rem]"
                style={{ borderBottom: '1px solid var(--wf-rule)', color: 'var(--wf-ink)' }}
              >
                <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4 flex-shrink-0" aria-hidden="true">
                  <path d="M4 10.5l4 4 8-9" stroke="var(--wf-line-w)" strokeWidth="2.5" strokeLinecap="square" />
                </svg>
                {perk}
              </li>
            ))}
          </ul>
          <PlateLink to={user ? '/dashboard' : '/register'} className="w-full justify-center">
            {user ? 'Open dashboard' : 'Get started free'}
          </PlateLink>
        </div>
      </div>
    </Section>
  );
}

// ─── Close ────────────────────────────────────────────────────────────────────

function Close({ user }) {
  return (
    <section
      className="px-6 py-32 md:py-44 text-center"
      style={{ background: 'var(--wf-ink)', color: 'var(--wf-canvas)' }}
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, ease }}
        className="max-w-2xl mx-auto"
      >
        <h2 className="wf-display text-4xl md:text-5xl mb-6 text-balance">
          Your degree will not plan itself.
        </h2>
        <p className="text-lg mb-11" style={{ opacity: 0.7 }}>
          Start with one term. Acadvo works out the rest of the route.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link
            to={user ? '/dashboard' : '/register'}
            className="wf-signage inline-flex items-center px-8 py-4 text-xs transition-transform duration-200 hover:-translate-y-0.5"
            style={{ background: 'var(--wf-canvas)', color: 'var(--wf-ink)' }}
          >
            {user ? 'Open dashboard' : 'Plan my degree'}
          </Link>
          {!user && (
            <Link
              to="/login"
              className="wf-signage inline-flex items-center px-8 py-4 text-xs"
              style={{ border: '2px solid currentColor' }}
            >
              Sign in
            </Link>
          )}
        </div>
      </motion.div>
    </section>
  );
}

function Footer({ user }) {
  return (
    <footer className="px-6 py-12" style={{ borderTop: '2px solid var(--wf-ink)' }}>
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-5">
        <div className="flex items-center gap-2.5">
          <span className="wf-bullet wf-bullet-live" aria-hidden="true">A</span>
          <span className="wf-signage text-sm" style={{ color: 'var(--wf-ink)' }}>acadvo</span>
        </div>
        <p className="text-sm" style={{ color: 'var(--wf-muted)' }}>
          Built for students, everywhere. &copy; {new Date().getFullYear()} Acadvo.
        </p>
        <div className="flex items-center gap-6">
          {user ? (
            <Link to="/dashboard" className="wf-signage text-[10px]" style={{ color: 'var(--wf-muted)' }}>Dashboard</Link>
          ) : (
            <>
              <Link to="/login" className="wf-signage text-[10px]" style={{ color: 'var(--wf-muted)' }}>Sign in</Link>
              <Link to="/register" className="wf-signage text-[10px]" style={{ color: 'var(--wf-muted)' }}>Get started</Link>
            </>
          )}
        </div>
      </div>
    </footer>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const STOPS = [
  { id: 'top',      label: 'Map' },
  { id: 'stuck',    label: 'The problem' },
  { id: 'try',      label: 'Try it' },
  { id: 'summary',  label: 'Summary' },
  { id: 'lines',    label: 'Lines' },
  { id: 'compare',  label: 'Compare' },
  { id: 'students', label: 'First run' },
  { id: 'pricing',  label: 'Pricing' },
  { id: 'faq',      label: 'FAQ' },
];

export default function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="wayfinding min-h-screen overflow-x-hidden">
      <LineRail stops={STOPS} />
      <Navbar user={user} />

      <Hero user={user} />
      <NetworksServed />
      <StuckSection />

      <Section id="try">
        <StationSign
          line="C"
          name="Plan a route"
          note="Pick a school and a program. The four-term plan assembles itself, the way Acadvo does it on day one."
          className="mb-12"
        />
        <PlanBuilder />
      </Section>

      <Manifesto />
      <ServiceSummary />
      <LinesSection />

      <Section id="compare" wide>
        <StationSign name="Compare" className="mb-12" />
        <ComparisonStrip />
      </Section>

      <Section id="students" wide>
        <StationSign
          name="Your first ten minutes"
          note="What setup actually asks for, before you sign up for anything."
          className="mb-12"
        />
        <FirstRun />
      </Section>

      <Pricing />

      <Section id="faq">
        <StationSign name="Questions" className="mb-12" />
        <FAQ />
      </Section>

      <Close user={user} />
      <Footer user={user} />
    </div>
  );
}
