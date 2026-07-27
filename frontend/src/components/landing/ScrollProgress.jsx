import { motion, useScroll, useSpring, useReducedMotion } from 'framer-motion';

/**
 * ScrollProgress — a fixed reading-progress bar pinned to the top of the
 * viewport. Fills left-to-right as the page scrolls. Sits at z-[60], above
 * the navbar (z-50) and other page chrome.
 *
 * A progress bar isn't motion-sickness-inducing, so it still renders under
 * prefers-reduced-motion — we just skip the spring smoothing and bind scaleX
 * directly to raw scroll progress in that case.
 */
export default function ScrollProgress() {
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll();

  const smooth = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 30,
    restDelta: 0.001,
  });

  const scaleX = reduceMotion ? scrollYProgress : smooth;

  return (
    <motion.div
      aria-hidden="true"
      className="fixed top-0 left-0 right-0 h-[3px] origin-left z-[60] pointer-events-none"
      style={{
        scaleX,
        background: 'linear-gradient(90deg, #FF8A00, #FFB347)',
      }}
    />
  );
}
