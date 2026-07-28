import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  motion,
  useScroll,
  useTransform,
  useMotionValue,
  useSpring,
  useInView,
  useReducedMotion,
  useMotionTemplate,
  useMotionValueEvent,
  animate,
} from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import ScrollProgress from '../components/landing/ScrollProgress';
import HeroMesh from '../components/landing/HeroMesh';
import FeatureBento from '../components/landing/FeatureBento';
import LiveAIMock from '../components/landing/LiveAIMock';
import ComparisonStrip from '../components/landing/ComparisonStrip';
import Testimonials from '../components/landing/Testimonials';
import FAQ from '../components/landing/FAQ';
import PlanBuilder from '../components/landing/PlanBuilder';
import FolioRail from '../components/landing/FolioRail';
import ThemeToggle from '../components/landing/ThemeToggle';
import TiltCard from '../components/landing/TiltCard';
import RevealText from '../components/landing/RevealText';

// ─── Shared animation presets ────────────────────────────────────────────────
const ease = [0.16, 1, 0.3, 1];

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: (delay = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, delay, ease },
  }),
};

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05 } },
};

const cardVariant = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease },
  },
};

// ─── Motion primitives ────────────────────────────────────────────────────────

/** Masked word-by-word headline reveal. Falls back to static text when the
 *  user prefers reduced motion. */
function SplitWords({ text, className = '', delay = 0, as: Tag = 'span' }) {
  const reduced = useReducedMotion();
  if (reduced) return <Tag className={className}>{text}</Tag>;
  return (
    <Tag className={className}>
      {text.split(' ').map((word, i) => (
        <span
          key={`${word}-${i}`}
          className="inline-block overflow-hidden align-bottom pb-[0.1em] -mb-[0.1em]"
        >
          <motion.span
            className="inline-block will-change-transform"
            initial={{ y: '115%' }}
            animate={{ y: 0 }}
            transition={{ duration: 0.75, delay: delay + i * 0.055, ease }}
          >
            {word}
            {' '}
          </motion.span>
        </span>
      ))}
    </Tag>
  );
}

/** Magnetic hover — the element leans toward the cursor, then springs back. */
function Magnetic({ children, strength = 0.3 }) {
  const ref = useRef(null);
  const reduced = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 260, damping: 18, mass: 0.5 });
  const sy = useSpring(y, { stiffness: 260, damping: 18, mass: 0.5 });

  function onMove(e) {
    if (reduced || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    x.set((e.clientX - (rect.left + rect.width / 2)) * strength);
    y.set((e.clientY - (rect.top + rect.height / 2)) * strength);
  }
  function onLeave() {
    x.set(0);
    y.set(0);
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ x: sx, y: sy }}
      className="inline-block"
    >
      {children}
    </motion.div>
  );
}

/** Animated integer that counts up when scrolled into view. */
function TickerNumber({ value, prefix = '', suffix = '', className = '' }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(reduced ? value : 0);

  useEffect(() => {
    if (!inView || reduced) return;
    const controls = animate(0, value, {
      duration: 1.4,
      ease,
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    return () => controls.stop();
  }, [inView, reduced, value]);

  return (
    <span ref={ref} className={`font-display tabular-nums ${className}`}>
      {prefix}
      {display}
      {suffix}
    </span>
  );
}

/** Editorial section eyebrow: number + letter-spaced label + hairline. */
function Eyebrow({ n, label, className = '' }) {
  return (
    <div className={`flex items-center gap-4 mb-10 ${className}`}>
      <span className="font-display text-primary-600 text-base">{n}</span>
      <span className="text-[11px] tracking-[0.28em] uppercase text-gray-400 whitespace-nowrap">{label}</span>
      <div className="h-px flex-1 bg-dark-600/70" />
    </div>
  );
}

/** Hairline-ruled masthead metadata strip (editorial magazine style). */
function MastheadMeta({ label, value }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[10px] tracking-[0.22em] uppercase text-gray-400">{label}</span>
      <span className="text-[10px] tracking-[0.22em] uppercase font-semibold text-dark-50">{value}</span>
    </div>
  );
}

function Masthead() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.9, duration: 0.8, ease }}
      className="hidden md:block absolute top-[72px] md:top-20 inset-x-0 z-10 px-6"
    >
      <div className="max-w-6xl mx-auto border-y border-dark-600/70 py-3.5 flex items-center justify-between gap-6">
        <MastheadMeta label="AI Academic Advisor" value="For Canadian Students" />
        <div className="hidden md:flex items-center gap-8">
          <div className="w-px h-8 bg-dark-600/70" />
          <MastheadMeta label="Universities" value="25+ Supported" />
          <div className="w-px h-8 bg-dark-600/70" />
          <MastheadMeta label="Price" value="$0 — Forever" />
        </div>
      </div>
    </motion.div>
  );
}

/** Small floating annotation card layered over the hero mockup. */
function FloatingChip({ className = '', delay = 0, children }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, delay, ease }}
      className={`absolute z-20 hidden lg:block ${className}`}
    >
      <motion.div
        animate={reduced ? {} : { y: [0, -9, 0] }}
        transition={{ duration: 5.5, repeat: Infinity, ease: 'easeInOut', delay }}
        className="rounded-xl border border-dark-600 bg-dark-800 shadow-editorial px-4 py-3"
      >
        {children}
      </motion.div>
    </motion.div>
  );
}

// ─── Manifesto — pinned, scroll-scrubbed statement (Apple-style) ──────────────

const MANIFESTO_TEXT =
  'University hands you a course catalog. Nobody hands you a plan. Acadvo turns four scattered years into one deliberate path — courses, projects, and applications all pointing at the same goal.';

function ManifestoSection({ manifestoRef }) {
  return (
    <section
      ref={manifestoRef}
      className="relative overflow-hidden bg-[#241E15] min-h-screen flex items-center px-6"
    >
      <span
        aria-hidden="true"
        className="manifesto-glyph artifact font-display text-[26rem] leading-none text-[#FF8A00] opacity-[0.07] -right-32 -top-16 select-none"
      >
        ✳
      </span>
      <div className="max-w-4xl mx-auto relative z-10 py-24">
        <p className="font-display text-3xl md:text-5xl lg:text-6xl leading-[1.18] text-[#F1EADB]">
          {MANIFESTO_TEXT.split(' ').map((word, i) => (
            <span key={i} className={`manifesto-word ${i >= 17 && i <= 19 ? 'text-[#FF8A00]' : ''}`}>
              {word}
              {' '}
            </span>
          ))}
        </p>
      </div>
    </section>
  );
}

// ─── Smooth scroll + scroll-driven motion (Lenis + GSAP, lazy-loaded) ─────────

function useLandingMotion(spotlightRef, manifestoRef) {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined;
    let lenis;
    let mm;
    let ctx;
    let rafId;
    let cancelled = false;

    (async () => {
      const [{ default: Lenis }, { default: gsap }, { ScrollTrigger }] = await Promise.all([
        import('lenis'),
        import('gsap'),
        import('gsap/ScrollTrigger'),
      ]);
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);

      // Inertia scrolling, wired into ScrollTrigger's update cycle.
      lenis = new Lenis({ duration: 1.05, smoothWheel: true });
      lenis.on('scroll', ScrollTrigger.update);
      const loop = (time) => {
        lenis.raf(time);
        rafId = requestAnimationFrame(loop);
      };
      rafId = requestAnimationFrame(loop);

      // All-viewport scroll effects: manifesto scrub, parallax, velocity skew.
      ctx = gsap.context(() => {
        // Manifesto: pin the ink panel while the statement lights up word by word.
        const mroot = manifestoRef.current;
        if (mroot) {
          const words = mroot.querySelectorAll('.manifesto-word');
          gsap.set(words, { opacity: 0.13 });
          gsap
            .timeline({
              scrollTrigger: {
                trigger: mroot,
                start: 'top top',
                end: '+=140%',
                pin: true,
                scrub: 0.5,
                anticipatePin: 1,
              },
            })
            .to(words, { opacity: 1, ease: 'none', duration: 3, stagger: { amount: 10 } })
            .to({}, { duration: 2 }); // hold before unpin
          const glyph = mroot.querySelector('.manifesto-glyph');
          if (glyph) {
            gsap.fromTo(
              glyph,
              { rotate: -18 },
              {
                rotate: 32,
                ease: 'none',
                scrollTrigger: { trigger: mroot, start: 'top bottom', end: 'bottom top', scrub: 1 },
              },
            );
          }
        }

        // Parallax artifacts: each drifts at its own depth as its section passes.
        gsap.utils.toArray('[data-parallax]').forEach((el) => {
          const speed = parseFloat(el.dataset.parallax || '1');
          gsap.fromTo(
            el,
            { y: 60 * speed },
            {
              y: -60 * speed,
              ease: 'none',
              scrollTrigger: {
                trigger: el.parentElement,
                start: 'top bottom',
                end: 'bottom top',
                scrub: 0.8,
              },
            },
          );
        });

        // Logo marquee skews with scroll velocity, then settles back.
        const marqueeViewport = document.querySelector('.marquee-viewport');
        if (marqueeViewport) {
          const proxy = { skew: 0 };
          const setter = gsap.quickSetter(marqueeViewport, 'skewX', 'deg');
          const clampV = gsap.utils.clamp(-8, 8);
          ScrollTrigger.create({
            onUpdate(self) {
              const skew = clampV(self.getVelocity() / -260);
              if (Math.abs(skew) > Math.abs(proxy.skew)) {
                proxy.skew = skew;
                gsap.to(proxy, {
                  skew: 0,
                  duration: 0.8,
                  ease: 'power3',
                  overwrite: true,
                  onUpdate: () => setter(proxy.skew),
                });
              }
            },
          });
        }
      });

      // Pinned story is desktop-only; mobile keeps the stacked layout.
      mm = gsap.matchMedia();
      mm.add('(min-width: 1024px)', () => {
        const root = spotlightRef.current;
        if (!root) return undefined;
        const panels = gsap.utils.toArray('.spot-panel', root);
        const texts = gsap.utils.toArray('.spot-text', root);
        const ticks = gsap.utils.toArray('.spot-tick', root);
        if (panels.length < 2) return undefined;

        gsap.set(panels.slice(1), { autoAlpha: 0, y: 90, scale: 0.96 });
        gsap.set(texts.slice(1), { autoAlpha: 0, y: 36 });
        gsap.set(ticks[0], { color: '#F07E00' });

        const tl = gsap.timeline({
          defaults: { ease: 'power2.inOut' },
          scrollTrigger: {
            trigger: root,
            start: 'top top',
            end: '+=220%',
            pin: true,
            scrub: 0.6,
            anticipatePin: 1,
          },
        });
        for (let i = 1; i < panels.length; i += 1) {
          tl.to({}, { duration: 0.45 }) // hold the current step
            .to(panels[i - 1], { autoAlpha: 0, y: -70, scale: 0.97, duration: 0.35 })
            .to(texts[i - 1], { autoAlpha: 0, y: -28, duration: 0.3 }, '<')
            .to(ticks[i - 1], { color: '', duration: 0.2, clearProps: 'color' }, '<')
            .to(panels[i], { autoAlpha: 1, y: 0, scale: 1, duration: 0.45 }, '<0.1')
            .to(texts[i], { autoAlpha: 1, y: 0, duration: 0.35 }, '<')
            .to(ticks[i], { color: '#F07E00', duration: 0.2 }, '<');
        }
        tl.to({}, { duration: 0.45 }); // hold the last step before unpinning

        return () => {
          tl.scrollTrigger?.kill();
          tl.kill();
        };
      });
    })();

    return () => {
      cancelled = true;
      if (rafId) cancelAnimationFrame(rafId);
      mm?.revert();
      ctx?.revert();
      lenis?.destroy();
    };
  }, [spotlightRef, manifestoRef]);
}

// ─── Data ─────────────────────────────────────────────────────────────────────
const steps = [
  {
    number: '01',
    title: 'Tell us your goals',
    description: 'Enter your university, program, and career target. Acadvo builds your personalized academic roadmap.',
  },
  {
    number: '02',
    title: 'Plan every step',
    description: 'Courses, projects, skills, and applications stay synchronized into a single, clear path to your career.',
  },
  {
    number: '03',
    title: 'Land the role',
    description: 'Track applications, prep for interviews, and walk into every opportunity ready to impress.',
  },
];

// ─── Components ───────────────────────────────────────────────────────────────

function Navbar({ user }) {
  // Transparent at the top; morphs to frosted glass once the page scrolls.
  const [scrolled, setScrolled] = useState(false);
  const { scrollY } = useScroll();
  useMotionValueEvent(scrollY, 'change', (v) => setScrolled(v > 32));

  return (
    <motion.nav
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease }}
      className={`fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 md:px-12 transition-all duration-500 ${
        scrolled
          ? 'py-2.5 backdrop-blur-xl bg-dark-950/80 border-b border-white/5 shadow-[0_8px_32px_rgb(36_30_21/0.08)]'
          : 'py-5 bg-transparent border-b border-transparent'
      }`}
    >
      <span className="text-xl font-bold font-display text-primary-600 tracking-tight">
        acadvo
      </span>

      <div className="hidden md:flex items-center gap-8 text-sm text-dark-300">
        <a href="#features" className="hover:text-white transition-colors">Features</a>
        <a href="#how-it-works" className="hover:text-white transition-colors">How it works</a>
        <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
      </div>

      <div className="flex items-center gap-3">
        <ThemeToggle />
        {user ? (
          <Link
            to="/dashboard"
            className="px-5 py-2 rounded-full bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold transition-colors"
          >
            Dashboard
          </Link>
        ) : (
          <>
            <Link to="/login" className="text-sm text-gray-400 hover:text-white transition-colors px-4 py-2">
              Sign in
            </Link>
            <Link
              to="/register"
              className="px-5 py-2 rounded-full bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold transition-colors"
            >
              Get started
            </Link>
          </>
        )}
      </div>
    </motion.nav>
  );
}

function MockDashboard() {
  return (
    <div className="relative mx-auto max-w-4xl">
      <div className="relative rounded-2xl border border-dark-600 bg-dark-800 overflow-hidden shadow-editorial">
        {/* Window chrome */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-dark-600 bg-dark-900/60">
          <div className="w-3 h-3 rounded-full bg-dark-500/60" />
          <div className="w-3 h-3 rounded-full bg-dark-500/60" />
          <div className="w-3 h-3 rounded-full bg-dark-500/60" />
          <div className="mx-auto text-xs text-dark-400">acadvo — dashboard</div>
        </div>

        <div className="flex">
          {/* Sidebar */}
          <div className="hidden sm:flex flex-col gap-1 w-44 p-3 border-r border-dark-600 bg-dark-900/40">
            {['Dashboard', 'Degree', 'Career', 'DSA Prep', 'Projects', 'Schedule'].map((item, i) => (
              <div
                key={item}
                className={`px-3 py-2 rounded-lg text-xs ${i === 0 ? 'bg-primary-500/10 text-primary-700' : 'text-dark-400'}`}
              >
                {item}
              </div>
            ))}
          </div>

          {/* Main content */}
          <div className="flex-1 p-4 grid grid-cols-2 md:grid-cols-3 gap-3">
            {/* GPA card */}
            <div className="col-span-1 rounded-xl border border-dark-600 bg-dark-900/30 p-3">
              <div className="text-xs text-dark-400 mb-1">Current GPA</div>
              <div className="text-2xl font-bold text-dark-50">3.8</div>
              <div className="text-xs text-emerald-600 mt-1">+0.2 this semester</div>
              <div className="mt-2 h-1.5 rounded-full bg-dark-700 overflow-hidden">
                <div className="h-full w-[80%] rounded-full bg-primary-500" />
              </div>
            </div>

            {/* Co-op card */}
            <div className="col-span-1 rounded-xl border border-dark-600 bg-dark-900/30 p-3">
              <div className="text-xs text-dark-400 mb-1">Applications</div>
              <div className="text-2xl font-bold text-dark-50">12</div>
              <div className="text-xs text-dark-300 mt-1">3 interviews scheduled</div>
              <div className="mt-2 flex gap-1">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className={`flex-1 h-1.5 rounded-full ${i < 3 ? 'bg-primary-500' : 'bg-dark-700'}`} />
                ))}
              </div>
            </div>

            {/* Degree progress */}
            <div className="col-span-2 md:col-span-1 rounded-xl border border-dark-600 bg-dark-900/30 p-3">
              <div className="text-xs text-dark-400 mb-1">Degree Progress</div>
              <div className="text-2xl font-bold text-dark-50">38%</div>
              <div className="text-xs text-dark-300 mt-1">24 / 63 credits done</div>
              <div className="mt-2 h-1.5 rounded-full bg-dark-700 overflow-hidden">
                <div className="h-full w-[38%] rounded-full bg-primary-500" />
              </div>
            </div>

            {/* Next actions */}
            <div className="col-span-2 md:col-span-2 rounded-xl border border-dark-600 bg-dark-900/30 p-3">
              <div className="text-xs text-dark-400 mb-2">Next Actions</div>
              {[
                { label: 'Submit midterm project — due Friday', tag: 'Deadline' },
                { label: 'Apply to summer internship at Shopify', tag: 'Career' },
                { label: 'Review notes: Week 8 lectures', tag: 'Study' },
              ].map((action) => (
                <div key={action.label} className="flex items-center justify-between py-1.5 border-b border-dark-600/60 last:border-0">
                  <span className="text-xs text-dark-200">{action.label}</span>
                  <span className="text-xs text-dark-400">{action.tag}</span>
                </div>
              ))}
            </div>

            {/* AI chat preview */}
            <div className="col-span-2 md:col-span-1 rounded-xl border border-dark-600 bg-dark-900/30 p-3">
              <div className="text-xs text-dark-400 mb-2">AI Advisor</div>
              <div className="text-xs text-dark-300 bg-primary-500/10 border border-primary-500/20 rounded-lg px-2 py-1.5">
                "Take STAT 2040 next — it's a prerequisite for 4 courses in your program."
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function HowItWorksSection() {
  return (
    <section id="how-it-works" className="relative py-32 px-6">
      <div className="max-w-5xl mx-auto relative">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          variants={fadeUp}
          custom={0}
          className="text-center mb-20"
        >
          <Eyebrow n="06" label="The path" />
          <RevealText
            as="h2"
            text="From enrollment to offer letter."
            accentFrom={3}
            className="font-display text-4xl md:text-5xl font-bold tracking-tight text-balance"
          />
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 md:gap-8">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-40px' }}
              variants={fadeUp}
              custom={i * 0.1}
              className="border-t border-dark-600 pt-6"
            >
              <span className="block font-display text-primary-600 text-lg mb-3">{step.number}</span>
              <h3 className="text-xl font-semibold text-dark-50 mb-3">{step.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{step.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CTASection() {
  const { user } = useAuth();

  return (
    <section className="relative py-40 px-6 overflow-hidden">
      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true }}
        variants={fadeUp}
        custom={0}
        className="relative max-w-4xl mx-auto text-center rounded-[2rem] border border-dark-600 card-rich px-6 py-20 md:px-16 overflow-hidden shadow-editorial"
      >
        {/* Warm aurora + grid inside the panel */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 aurora-warm opacity-90" />
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-editorial-grid" />
        <div aria-hidden="true" className="pointer-events-none absolute -inset-x-10 -top-24 h-64 bg-[radial-gradient(ellipse_at_top,rgba(255,138,0,0.22),transparent_65%)] blur-2xl" />
        <div className="relative">
        <RevealText
          as="h2"
          text="Your degree won't plan itself."
          accentFrom={3}
          className="font-display text-5xl md:text-6xl font-bold tracking-tight mb-6 text-balance"
        />
        <p className="text-gray-400 text-lg mb-10 max-w-xl mx-auto leading-relaxed">
          Stop reacting to deadlines. Start planning ahead. Acadvo keeps your entire academic life in one place so nothing slips through.
        </p>

        {user ? (
          <Link
            to="/dashboard"
            className="group inline-flex items-center gap-2 px-10 py-4 rounded-full bg-primary-600 hover:bg-primary-700 text-white font-semibold text-lg transition-colors"
          >
            Go to Dashboard
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1">
              <path fillRule="evenodd" d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z" clipRule="evenodd" />
            </svg>
          </Link>
        ) : (
          <div className="flex items-center justify-center gap-4">
            <Link
              to="/register"
              className="group inline-flex items-center gap-2 px-10 py-4 rounded-full bg-primary-600 hover:bg-primary-700 text-white font-semibold text-lg transition-colors"
            >
              Get started free
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 transition-transform duration-300 group-hover:translate-x-1">
                <path fillRule="evenodd" d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z" clipRule="evenodd" />
              </svg>
            </Link>
            <Link
              to="/login"
              className="px-8 py-4 rounded-full border border-white/10 bg-white/5 text-white font-semibold text-lg hover:bg-white/10 transition-colors"
            >
              Sign in
            </Link>
          </div>
        )}
        </div>
      </motion.div>
    </section>
  );
}

// ─── Problem section ──────────────────────────────────────────────────────────

const PAINS = [
  { text: "Tracking degree requirements in a spreadsheet that's always out of date" },
  { text: 'Juggling 5 different apps for deadlines, grades, and job applications' },
  { text: 'Missing prerequisites because nothing talks to each other' },
  { text: "No idea where you stand until it's too late to fix it" },
];

function ProblemSection() {
  return (
    <section className="relative py-32 px-6 overflow-hidden">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          variants={fadeUp}
          custom={0}
          className="text-center mb-16"
        >
          <Eyebrow n="00" label="The problem" className="max-w-4xl mx-auto" />
          <RevealText
            as="h2"
            text="Sound familiar?"
            className="font-display text-4xl md:text-5xl font-bold tracking-tight mb-4 text-balance"
          />
          <p className="text-gray-400 text-lg max-w-xl mx-auto">
            You're not disorganized. Your tools are.
          </p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-60px' }}
          variants={stagger}
          className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-16"
        >
          {PAINS.map((pain) => (
            <motion.div
              key={pain.text}
              variants={cardVariant}
              className="flex items-start gap-4 p-5 rounded-xl border border-dark-600 bg-dark-800"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-dark-400 flex-shrink-0 mt-0.5">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
              </svg>
              <p className="text-gray-300 leading-relaxed">{pain.text}</p>
            </motion.div>
          ))}
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeUp}
          custom={0}
          className="text-center"
        >
          <div className="inline-flex items-center gap-3 text-primary-700 text-lg font-semibold">
            <div className="h-px w-12 bg-dark-600" />
            Acadvo brings it all together.
            <div className="h-px w-12 bg-dark-600" />
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ─── Feature spotlight ────────────────────────────────────────────────────────

function DegreePlannerMock() {
  const semesters = [
    { label: 'Year 1 — Fall', courses: ['CALC I', 'INTRO CS', 'ENGLISH'], done: true },
    { label: 'Year 1 — Winter', courses: ['CALC II', 'DATA STRUCT', 'STATS I'], done: true },
    { label: 'Year 2 — Fall', courses: ['ALGORITHMS', 'OS', 'ELECTIVE'], done: false },
    { label: 'Year 2 — Winter', courses: ['DATABASES', 'NETWORKS', 'ELECTIVE'], done: false },
  ];
  return (
    <div className="relative rounded-2xl border border-dark-600 bg-dark-800 overflow-hidden shadow-editorial">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-dark-600 bg-dark-900/60">
        <div className="w-3 h-3 rounded-full bg-dark-500/60" />
        <div className="w-3 h-3 rounded-full bg-dark-500/60" />
        <div className="w-3 h-3 rounded-full bg-dark-500/60" />
        <span className="mx-auto text-xs text-dark-400">acadvo — degree planner</span>
      </div>
      <div className="p-4 grid grid-cols-2 gap-3">
        {semesters.map((sem) => (
          <div key={sem.label} className={`rounded-xl border p-3 ${sem.done ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-dark-600 bg-dark-900/30'}`}>
            <div className={`text-xs font-semibold mb-2 ${sem.done ? 'text-emerald-400' : 'text-gray-400'}`}>{sem.label}</div>
            <div className="flex flex-col gap-1">
              {sem.courses.map((c) => (
                <div key={c} className="flex items-center gap-2">
                  <div className={`w-1.5 h-1.5 rounded-full ${sem.done ? 'bg-emerald-400' : 'bg-gray-600'}`} />
                  <span className="text-xs text-gray-300">{c}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="px-4 pb-4">
        <div className="rounded-xl border border-primary-500/20 bg-primary-500/5 p-3">
          <div className="text-xs text-primary-700 font-semibold mb-1">Degree progress</div>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-1.5 rounded-full bg-dark-700 overflow-hidden">
              <div className="h-full w-[52%] rounded-full bg-primary-500" />
            </div>
            <span className="text-xs text-gray-400">52%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function CareerPipelineMock() {
  const stages = [
    { label: 'Applied', color: 'text-dark-300 border-dark-600 bg-dark-900/30', items: ['Shopify — SWE Intern', 'RBC Ventures — Analyst'] },
    { label: 'Interview', color: 'text-amber-600 border-amber-500/20 bg-amber-500/5', items: ['Wealthsimple — Co-op'] },
    { label: 'Offer', color: 'text-emerald-600 border-emerald-500/20 bg-emerald-500/5', items: ['TD Lab — Developer'] },
  ];
  return (
    <div className="relative rounded-2xl border border-dark-600 bg-dark-800 overflow-hidden shadow-editorial">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-dark-600 bg-dark-900/60">
        <div className="w-3 h-3 rounded-full bg-dark-500/60" />
        <div className="w-3 h-3 rounded-full bg-dark-500/60" />
        <div className="w-3 h-3 rounded-full bg-dark-500/60" />
        <span className="mx-auto text-xs text-dark-400">acadvo — internship pipeline</span>
      </div>
      <div className="p-4 grid grid-cols-3 gap-3">
        {stages.map((stage) => (
          <div key={stage.label} className={`rounded-xl border p-3 ${stage.color}`}>
            <div className="text-xs font-semibold mb-3">{stage.label}</div>
            <div className="flex flex-col gap-2">
              {stage.items.map((item) => (
                <div key={item} className="rounded-lg bg-dark-900/40 border border-dark-600/60 p-2">
                  <p className="text-xs text-gray-300 leading-snug">{item}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="px-4 pb-4">
        <div className="rounded-xl border border-dark-600 bg-dark-900/30 p-3 flex items-center justify-between">
          <span className="text-xs text-gray-400">4 applications this week</span>
          <span className="text-xs text-emerald-600">1 offer received</span>
        </div>
      </div>
    </div>
  );
}

const SPOTLIGHTS = [
  {
    tag: 'Degree Planning',
    headline: 'Never miss a prerequisite again.',
    body: "Map every course requirement, track what you've completed, and see exactly what's left, organized by semester, program, and year.",
    bullets: ['Visual course map with prerequisites', 'Automatic progress tracking', 'Works for any program or university'],
    Mock: DegreePlannerMock,
    flip: false,
  },
  {
    tag: 'Co-op / Internship Pipeline',
    headline: 'Your job search, finally organized.',
    body: 'Track every application from first click to offer letter. Know exactly where you stand across every company, every role, every stage.',
    bullets: ['Kanban pipeline from applied to offer', 'Deadline reminders and follow-up tracking', 'Works for internships, co-ops, and full-time'],
    Mock: CareerPipelineMock,
    flip: true,
  },
  {
    tag: 'AI Academic Advisor',
    headline: 'An advisor that actually knows your situation.',
    body: 'Ask anything. Get answers tailored to your degree, your goals, and your progress — not generic advice from a pamphlet.',
    bullets: ['Course recommendations based on your goals', 'Prerequisite and graduation gap detection', 'Career-aware suggestions'],
    Mock: LiveAIMock,
    flip: false,
  },
];

function SpotlightText({ s }) {
  return (
    <>
      <div className="text-primary-700 text-sm font-semibold mb-4">
        {s.tag}
      </div>
      <h3 className="text-3xl md:text-4xl font-bold tracking-tight text-dark-50 mb-4">{s.headline}</h3>
      <p className="text-gray-400 text-lg leading-relaxed mb-6">{s.body}</p>
      <ul className="flex flex-col gap-3">
        {s.bullets.map((b) => (
          <li key={b} className="flex items-start gap-3 text-gray-300 text-sm">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-primary-600 flex-shrink-0 mt-0.5">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
            </svg>
            {b}
          </li>
        ))}
      </ul>
    </>
  );
}

/** Stacked spotlights — mobile layout and the reduced-motion fallback. */
function SpotlightsStacked({ className = '' }) {
  return (
    <section className={`py-24 px-6 ${className}`}>
      <div className="max-w-6xl mx-auto flex flex-col gap-32">
        {SPOTLIGHTS.map((s) => (
          <motion.div
            key={s.tag}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-80px' }}
            variants={stagger}
            className={`grid grid-cols-1 lg:grid-cols-2 gap-12 items-center ${s.flip ? 'lg:[&>*:first-child]:order-2' : ''}`}
          >
            <motion.div variants={fadeUp} custom={0}>
              <SpotlightText s={s} />
            </motion.div>
            <motion.div variants={fadeUp} custom={0.1} className="relative">
              <TiltCard className="w-full" max={6}><s.Mock /></TiltCard>
            </motion.div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

/** Desktop: one pinned viewport where the three product stories scrub past
 *  each other as the user scrolls (GSAP ScrollTrigger, wired in
 *  useLandingMotion). Mobile and reduced-motion get the stacked layout. */
function FeatureSpotlightSection({ pinRef }) {
  const reduced = useReducedMotion();
  if (reduced) return <SpotlightsStacked />;

  return (
    <>
      <section ref={pinRef} className="hidden lg:flex h-screen items-center px-6 overflow-hidden">
        <div className="max-w-6xl mx-auto w-full grid grid-cols-[auto,1fr,1.15fr] gap-14 items-center">
          {/* Progress rail */}
          <div className="flex flex-col gap-8" aria-hidden="true">
            {SPOTLIGHTS.map((s, i) => (
              <span key={s.tag} className="spot-tick font-display text-xl text-dark-500">
                0{i + 1}
              </span>
            ))}
          </div>

          {/* Text stack */}
          <div className="relative h-[380px]">
            {SPOTLIGHTS.map((s) => (
              <div key={s.tag} className="spot-text absolute inset-0 flex flex-col justify-center">
                <SpotlightText s={s} />
              </div>
            ))}
          </div>

          {/* Mock stack */}
          <div className="relative h-[460px]">
            {SPOTLIGHTS.map((s) => (
              <div key={s.tag} className="spot-panel absolute inset-0 flex items-center">
                <div className="w-full">
                  <TiltCard className="w-full" max={6}><s.Mock /></TiltCard>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <SpotlightsStacked className="lg:hidden" />
    </>
  );
}

// ─── Stats strip ──────────────────────────────────────────────────────────────

function SpecRow({ label, children }) {
  return (
    <div className="flex items-center justify-between py-5 border-b border-dark-600/60 last:border-0">
      <span className="text-[11px] tracking-[0.28em] uppercase text-gray-400">{label}</span>
      {children}
    </div>
  );
}

/** Editorial spec-sheet: label-left / value-right rows split by hairlines. */
function StatsStrip() {
  return (
    <section className="py-20 px-6">
      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: '-60px' }}
        variants={fadeUp}
        custom={0}
        className="max-w-3xl mx-auto"
      >
        <Eyebrow n="02" label="Acadvo, on paper" />
        <div className="border-y border-dark-600/60">
          <SpecRow label="Canadian universities">
            <TickerNumber value={25} suffix="+" className="text-3xl md:text-4xl text-dark-50" />
          </SpecRow>
          <SpecRow label="Actions the AI can take">
            <TickerNumber value={15} className="text-3xl md:text-4xl text-dark-50" />
          </SpecRow>
          <SpecRow label="DSA interview patterns">
            <TickerNumber value={12} className="text-3xl md:text-4xl text-dark-50" />
          </SpecRow>
          <SpecRow label="Price, forever">
            <span className="font-display text-3xl md:text-4xl text-primary-600">$0</span>
          </SpecRow>
        </div>
      </motion.div>
    </section>
  );
}

// ─── Pricing ──────────────────────────────────────────────────────────────────

function PricingSection() {
  const perks = [
    'Degree planner for any program',
    'GPA tracker & grade simulator',
    'Co-op / internship pipeline',
    'AI course advisor',
    'DSA interview prep tracks',
    'Project & milestone tracker',
    'Works at any university',
    'No credit card required',
  ];

  return (
    <section id="pricing" className="py-28 px-6">
      <div className="max-w-lg mx-auto">
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeUp}
          custom={0}
          className="text-center mb-12"
        >
          <Eyebrow n="07" label="Pricing" />
          <RevealText
            as="h2"
            text="Free. For students."
            accentFrom={1}
            className="font-display text-4xl md:text-5xl font-bold tracking-tight text-balance"
          />
          <p className="text-gray-400 mt-4 text-lg">Because you're already paying enough tuition.</p>
        </motion.div>

        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeUp}
          custom={0.1}
          className="relative rounded-2xl border border-dark-600 card-rich overflow-hidden shadow-editorial"
        >
          <div aria-hidden="true" className="pointer-events-none absolute -inset-x-8 -top-16 h-40 bg-[radial-gradient(ellipse_at_top,rgba(255,138,0,0.18),transparent_65%)] blur-2xl" />
          <div className="relative p-8">
            <div className="flex items-end gap-2 mb-1">
              <span className="text-6xl font-bold text-dark-50">$0</span>
              <span className="text-gray-400 mb-2">/ forever</span>
            </div>
            <p className="text-sm text-gray-500 mb-8">Everything included. No hidden tiers.</p>

            <ul className="flex flex-col gap-3 mb-8">
              {perks.map((perk) => (
                <li key={perk} className="flex items-center gap-3 text-gray-300 text-sm">
                  <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-emerald-600 flex-shrink-0">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                  </svg>
                  {perk}
                </li>
              ))}
            </ul>

            <Link
              to="/register"
              className="block w-full text-center px-8 py-4 rounded-full bg-primary-600 hover:bg-primary-700 text-white font-semibold text-lg transition-colors"
            >
              Get started free
            </Link>
            <p className="text-center text-xs text-gray-600 mt-3">No credit card. No commitment. Just get organized.</p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ─── Universities marquee ─────────────────────────────────────────────────────

const UNIVERSITIES = [
  { name: 'University of Toronto',   logo: '/logos/uoft.svg',     invert: true  },
  { name: 'UBC',                     logo: '/logos/ubc.svg',      invert: true  },
  { name: 'McGill University',       logo: '/logos/mcgill.png'                  },
  { name: 'Western University',      logo: '/logos/western.svg'                 },
  { name: 'York University',         logo: '/logos/york.png',     invert: true  },
  { name: 'Toronto Metropolitan',    logo: '/logos/tmu.svg'                     },
  { name: "Queen's University",      logo: '/logos/queens.svg'                  },
  { name: 'University of Waterloo',  logo: '/logos/waterloo.svg', invert: true  },
  { name: 'McMaster University',     logo: '/logos/mcmaster.png'                },
  { name: 'University of Ottawa',    logo: '/logos/ottawa.svg',   invert: true  },
  { name: 'Carleton University',     logo: '/logos/carleton.svg', invert: true  },
  { name: 'Concordia University',    logo: '/logos/concordia.svg',invert: true  },
  { name: 'Simon Fraser University', logo: '/logos/sfu.png'                     },
  { name: 'University of Calgary',   logo: '/logos/ucalgary.svg'                },
  { name: 'Dalhousie University',    logo: '/logos/dal.svg',      invert: true  },
];

function UniversityBadge({ uni }) {
  return (
    <div className="flex-shrink-0 mx-10 h-10 select-none flex items-center justify-center">
      <img
        src={uni.logo}
        alt={uni.name}
        className={`max-h-full max-w-[150px] w-auto object-contain opacity-70 hover:opacity-100 transition-opacity duration-300 ${uni.invert ? 'logo-dark-invert' : ''}`}
      />
    </div>
  );
}

function UniversitiesSection({ duration = 60 }) {
  const doubled = [...UNIVERSITIES, ...UNIVERSITIES];

  return (
    <section className="py-16">
      <motion.p
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, ease }}
        className="text-center text-sm text-gray-500 mb-10 tracking-widest uppercase"
      >
        Built for students at
      </motion.p>

      <div className="marquee-viewport relative h-14 overflow-hidden will-change-transform">
        <div
          className="absolute flex w-max items-center h-full marquee-left"
          style={{ '--marquee-duration': `${duration}s` }}
        >
          {doubled.map((uni, i) => (
            <UniversityBadge key={i} uni={uni} />
          ))}
        </div>
        <div className="pointer-events-none absolute inset-y-0 left-0 w-40 bg-gradient-to-r from-dark-950 to-transparent z-10" />
        <div className="pointer-events-none absolute inset-y-0 right-0 w-40 bg-gradient-to-l from-dark-950 to-transparent z-10" />
      </div>
    </section>
  );
}

function Footer({ user }) {
  return (
    <footer className="border-t border-white/5 pt-12 pb-6 px-6 overflow-hidden">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 mb-10">
        <p className="text-sm text-gray-600">
          Built for students, everywhere. &copy; {new Date().getFullYear()} Acadvo.
        </p>
        <div className="flex items-center gap-6 text-sm text-gray-600">
          {user ? (
            <Link to="/dashboard" className="hover:text-gray-400 transition-colors">Dashboard</Link>
          ) : (
            <>
              <Link to="/login" className="hover:text-gray-400 transition-colors">Sign in</Link>
              <Link to="/register" className="hover:text-gray-400 transition-colors">Get started</Link>
            </>
          )}
        </div>
      </div>
      {/* Giant editorial wordmark, bleeding toward the edges */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-40px' }}
        transition={{ duration: 0.9, ease }}
        className="max-w-7xl mx-auto"
      >
        <div className="font-display font-bold text-primary-600 leading-[0.82] tracking-tight text-center text-[clamp(2rem,6vw,4rem)] select-none -mb-1 md:-mb-2">
          acadvo
        </div>
      </motion.div>
    </footer>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

// Curated section index for the left-margin folio rail (numbers mirror the
// editorial eyebrows). Each id maps to a section (or wrapper) in the body.
const FOLIO_ITEMS = [
  { id: 'problem',      n: '00', label: 'Problem' },
  { id: 'try',          n: '01', label: 'Try it' },
  { id: 'stats',        n: '02', label: 'Overview' },
  { id: 'features',     n: '03', label: 'Toolkit' },
  { id: 'compare',      n: '04', label: 'Compare' },
  { id: 'students',     n: '05', label: 'Students' },
  { id: 'how-it-works', n: '06', label: 'The path' },
  { id: 'pricing',      n: '07', label: 'Pricing' },
  { id: 'faq',          n: '08', label: 'FAQ' },
];

export default function LandingPage() {
  const { user } = useAuth();

  const { scrollY } = useScroll();
  const heroY = useTransform(scrollY, [0, 600], [0, 80]);
  const heroOpacity = useTransform(scrollY, [0, 450], [1, 0]);
  const heroScale = useTransform(scrollY, [0, 600], [1, 0.96]);
  const heroBlurPx = useTransform(scrollY, [0, 500], [0, 10]);
  const heroFilter = useMotionTemplate`blur(${heroBlurPx}px)`;

  // Hero mockup settles out of a 3D tilt as it scrolls into view.
  const mockWrapRef = useRef(null);
  const { scrollYProgress: mockProgress } = useScroll({
    target: mockWrapRef,
    offset: ['start 95%', 'start 45%'],
  });
  const mockRotateX = useTransform(mockProgress, [0, 1], [14, 0]);
  const mockScale = useTransform(mockProgress, [0, 1], [0.95, 1]);

  // Smooth scroll + pinned spotlight story + manifesto scrub.
  const spotlightPinRef = useRef(null);
  const manifestoRef = useRef(null);
  useLandingMotion(spotlightPinRef, manifestoRef);

  // The pinned spotlight has its own left-edge progress ticks, which sit right
  // where the FolioRail lives — hide the rail while that section holds the view.
  const [spotlightActive, setSpotlightActive] = useState(false);
  useEffect(() => {
    const el = spotlightPinRef.current;
    if (!el) return undefined;
    const io = new IntersectionObserver(
      ([entry]) => setSpotlightActive(entry.isIntersecting),
      { rootMargin: '-30% 0px -30% 0px' }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div className="min-h-screen bg-dark-950 text-dark-50 overflow-x-hidden">
      <div className="grain-overlay" aria-hidden="true" />
      <ScrollProgress />
      <FolioRail items={FOLIO_ITEMS} hidden={spotlightActive} />
      <Navbar user={user} />

      {/* ── Hero ── */}
      <section
        className="relative min-h-screen flex flex-col items-center justify-center pt-32 md:pt-48 overflow-hidden"
      >
        {/* Layered background: animated warm mesh + ruled grid for depth */}
        <HeroMesh />
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-editorial-grid" />
        <Masthead />

        <motion.div
          style={{ y: heroY, opacity: heroOpacity, scale: heroScale, filter: heroFilter }}
          className="relative z-10 flex flex-col items-center text-center px-6 max-w-5xl mx-auto"
        >
          {/* Headline — masked word-by-word reveal */}
          <h1 className="text-5xl/[1.22] md:text-6xl/[1.22] lg:text-7xl/[1.22] font-bold tracking-tight mb-6">
            <SplitWords text="Graduate on time." className="block" delay={0.1} />
            <SplitWords text="Land the internship." className="block" delay={0.28} />
            <SplitWords
              text="Do it all from one place."
              className="block font-display text-gradient-warm"
              delay={0.48}
            />
          </h1>

          {/* Subtext */}
          <motion.p
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.9, delay: 0.2, ease }}
            className="text-xl md:text-2xl text-gray-400 max-w-2xl leading-relaxed mb-10"
          >
            Track your degree, prep for interviews, and manage your job applications in one platform built for students.
          </motion.p>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.35, ease }}
            className="flex items-center gap-4"
          >
            {user ? (
              <Link
                to="/dashboard"
                className="px-9 py-4 rounded-full bg-primary-600 hover:bg-primary-700 text-white font-semibold text-lg transition-colors"
              >
                Go to Dashboard →
              </Link>
            ) : (
              <>
                <Magnetic>
                  <Link
                    to="/register"
                    className="inline-block px-9 py-4 rounded-full bg-primary-600 hover:bg-primary-700 text-white font-semibold text-lg transition-colors"
                  >
                    Get started free
                  </Link>
                </Magnetic>
                <Link
                  to="/login"
                  className="px-8 py-4 rounded-full border border-white/10 bg-white/5 text-white font-semibold text-lg hover:bg-white/10 transition-colors"
                >
                  Sign in
                </Link>
              </>
            )}
          </motion.div>

          {/* Mock dashboard preview — settles out of a 3D tilt as it scrolls in */}
          <motion.div
            initial={{ opacity: 0, y: 60 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1.1, delay: 0.55, ease }}
            className="mt-20 w-full relative"
          >
            {/* Ambient glow behind the product */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -inset-x-20 -top-12 bottom-0 bg-[radial-gradient(ellipse_at_top,rgba(255,138,0,0.18),transparent_65%)] blur-2xl"
            />
            <div ref={mockWrapRef} className="relative" style={{ perspective: 1400 }}>
              <motion.div style={{ rotateX: mockRotateX, scale: mockScale, transformStyle: 'preserve-3d' }}>
                <MockDashboard />
              </motion.div>

              <FloatingChip className="-right-4 xl:-right-10 top-8" delay={1.1}>
                <div className="text-xs text-gray-400 mb-0.5">AI Advisor</div>
                <div className="text-sm text-dark-50 font-semibold">STAT 2040 added to Fall plan</div>
              </FloatingChip>
              <FloatingChip className="-left-6 xl:-left-12 bottom-14" delay={1.35}>
                <div className="text-xs text-gray-400 mb-0.5">Pipeline</div>
                <div className="text-sm text-dark-50 font-semibold">Interview scheduled — Wealthsimple</div>
              </FloatingChip>
            </div>
          </motion.div>
        </motion.div>
      </section>

      <div id="problem"><ProblemSection /></div>
      <div id="try"><PlanBuilder /></div>
      <UniversitiesSection duration={60} />
      <ManifestoSection manifestoRef={manifestoRef} />
      <div id="stats"><StatsStrip /></div>
      <FeatureBento />
      <FeatureSpotlightSection pinRef={spotlightPinRef} />
      <div id="compare"><ComparisonStrip /></div>
      <div id="students"><Testimonials /></div>
      <HowItWorksSection />
      <PricingSection />
      <FAQ />
      <CTASection />
      <Footer user={user} />
    </div>
  );
}
