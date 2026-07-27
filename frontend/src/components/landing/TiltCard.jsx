import { useCallback, useRef } from 'react';
import {
  motion,
  useMotionValue,
  useMotionTemplate,
  useSpring,
  useReducedMotion,
} from 'framer-motion';

/**
 * TiltCard — a reusable wrapper that gives its children a subtle 3D
 * pointer-tilt. The card leans toward the cursor with a soft spring and levels
 * out on mouse-leave. Used to wrap product-mock cards on the landing page.
 *
 * The root establishes a perspective; an inner `preserve-3d` layer receives the
 * rotateX/rotateY so children (and an optional glare highlight) turn together.
 * Children stay fully interactive — the wrapper only reads mousemove.
 *
 * Respects prefers-reduced-motion: when set, children render in a plain div
 * with no tilt, no glare, and no listeners.
 *
 * @param {object}  props
 * @param {React.ReactNode} props.children
 * @param {string}  [props.className]  passed through to the root element
 * @param {number}  [props.max=8]      max tilt in degrees on each axis
 * @param {boolean} [props.glare=true] enable the pointer-following highlight
 */
export default function TiltCard({ children, className = '', max = 8, glare = true }) {
  const prefersReducedMotion = useReducedMotion();

  const ref = useRef(null);

  // Raw pointer-driven targets (in degrees / 0–100%), smoothed via springs.
  const rotateXRaw = useMotionValue(0);
  const rotateYRaw = useMotionValue(0);
  const glareXRaw = useMotionValue(50);
  const glareYRaw = useMotionValue(50);

  const spring = { stiffness: 150, damping: 15, mass: 0.4 };
  const rotateX = useSpring(rotateXRaw, spring);
  const rotateY = useSpring(rotateYRaw, spring);
  const glareX = useSpring(glareXRaw, spring);
  const glareY = useSpring(glareYRaw, spring);

  // Radial highlight that follows the cursor across the tilt layer.
  const glareBackground = useMotionTemplate`radial-gradient(circle at ${glareX}% ${glareY}%, rgba(255,255,255,0.9), transparent 60%)`;

  const handleMouseMove = useCallback(
    (event) => {
      const node = ref.current;
      if (!node) return;

      const rect = node.getBoundingClientRect();
      if (!rect.width || !rect.height) return;

      // Pointer position relative to the card center, normalized to [-0.5, 0.5].
      const px = (event.clientX - rect.left) / rect.width - 0.5;
      const py = (event.clientY - rect.top) / rect.height - 0.5;

      // Horizontal pointer -> rotateY; vertical pointer -> rotateX.
      // Negate rotateX so the top leans back toward the cursor (feels physical).
      rotateYRaw.set(px * max * 2);
      rotateXRaw.set(-py * max * 2);

      glareXRaw.set((px + 0.5) * 100);
      glareYRaw.set((py + 0.5) * 100);
    },
    [max, rotateXRaw, rotateYRaw, glareXRaw, glareYRaw],
  );

  const handleMouseLeave = useCallback(() => {
    rotateXRaw.set(0);
    rotateYRaw.set(0);
    glareXRaw.set(50);
    glareYRaw.set(50);
  }, [rotateXRaw, rotateYRaw, glareXRaw, glareYRaw]);

  // Reduced motion: no tilt, no glare, no listeners.
  if (prefersReducedMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <div
      ref={ref}
      className={className}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ perspective: 1000 }}
    >
      <motion.div
        className="relative h-full w-full"
        style={{
          rotateX,
          rotateY,
          transformStyle: 'preserve-3d',
        }}
      >
        {children}

        {glare && (
          <motion.div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              background: glareBackground,
              opacity: 0.06,
              transform: 'translateZ(1px)',
            }}
          />
        )}
      </motion.div>
    </div>
  );
}
