import { useEffect, useState } from 'react';
import { motion, useMotionValue, useSpring, useReducedMotion } from 'framer-motion';

/**
 * CustomCursor — a refined, design-studio-style trailing accent that follows
 * the pointer with a springy lag and grows over interactive targets.
 *
 * This is ADDITIVE: the native cursor is never hidden, so usability never
 * regresses. It renders at z-[70] (above the navbar z-50 and scroll bar z-[60]),
 * is aria-hidden and pointer-events-none.
 *
 * Gated to fine (mouse) pointers only, and disabled under prefers-reduced-motion —
 * in both cases we render nothing. Animation is transform-only for performance.
 */

const HOVER_SELECTOR = 'a, button, [role="button"], input, select, textarea, [data-cursor="hover"]';

export default function CustomCursor() {
  const reduceMotion = useReducedMotion();

  // Only enable on devices with a fine (mouse) pointer.
  const [finePointer, setFinePointer] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mq = window.matchMedia('(pointer: fine)');
    const update = () => setFinePointer(mq.matches);
    update();
    // Safari <14 uses addListener/removeListener.
    if (mq.addEventListener) mq.addEventListener('change', update);
    else mq.addListener(update);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', update);
      else mq.removeListener(update);
    };
  }, []);

  const enabled = finePointer && !reduceMotion;

  // Raw pointer position -> springy ring position.
  const mouseX = useMotionValue(-100);
  const mouseY = useMotionValue(-100);
  const springConfig = { stiffness: 500, damping: 40, mass: 0.6 };
  const ringX = useSpring(mouseX, springConfig);
  const ringY = useSpring(mouseY, springConfig);

  const [hovering, setHovering] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!enabled) return undefined;

    const handleMove = (e) => {
      mouseX.set(e.clientX);
      mouseY.set(e.clientY);
      setVisible(true);
    };
    const handleOver = (e) => {
      const target = e.target;
      if (target && typeof target.closest === 'function' && target.closest(HOVER_SELECTOR)) {
        setHovering(true);
      }
    };
    const handleOut = (e) => {
      const target = e.target;
      if (target && typeof target.closest === 'function' && target.closest(HOVER_SELECTOR)) {
        // Only clear if we're actually leaving the interactive target.
        const related = e.relatedTarget;
        if (!related || typeof related.closest !== 'function' || !related.closest(HOVER_SELECTOR)) {
          setHovering(false);
        }
      }
    };
    const handleLeave = () => setVisible(false);
    const handleEnter = () => setVisible(true);

    window.addEventListener('mousemove', handleMove, { passive: true });
    window.addEventListener('mouseover', handleOver, { passive: true });
    window.addEventListener('mouseout', handleOut, { passive: true });
    document.addEventListener('mouseleave', handleLeave);
    document.addEventListener('mouseenter', handleEnter);

    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseover', handleOver);
      window.removeEventListener('mouseout', handleOut);
      document.removeEventListener('mouseleave', handleLeave);
      document.removeEventListener('mouseenter', handleEnter);
    };
  }, [enabled, mouseX, mouseY]);

  if (!enabled) return null;

  return (
    <motion.div
      aria-hidden="true"
      className="fixed top-0 left-0 z-[70] pointer-events-none"
      style={{ x: ringX, y: ringY }}
    >
      <motion.div
        className="rounded-full border border-primary-500/60"
        style={{
          width: 28,
          height: 28,
          // Center on the pointer; scaling from center keeps it anchored.
          translateX: '-50%',
          translateY: '-50%',
        }}
        animate={{
          scale: hovering ? 1.8 : 1,
          opacity: visible ? 1 : 0,
          backgroundColor: hovering ? 'rgba(255, 138, 0, 0.15)' : 'rgba(255, 138, 0, 0)',
        }}
        transition={{
          scale: { type: 'spring', stiffness: 400, damping: 28 },
          opacity: { duration: 0.2 },
          backgroundColor: { duration: 0.2 },
        }}
      >
        {/* Tiny center dot for a low-profile default look. */}
        <motion.span
          className="absolute left-1/2 top-1/2 rounded-full bg-primary-500"
          style={{ width: 4, height: 4, translateX: '-50%', translateY: '-50%' }}
          animate={{ opacity: hovering ? 0 : 0.9 }}
          transition={{ duration: 0.2 }}
        />
      </motion.div>
    </motion.div>
  );
}
