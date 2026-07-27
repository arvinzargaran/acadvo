import { motion, useReducedMotion } from 'framer-motion';

/**
 * HeroMesh — an animated, heavily-blurred warm amber gradient mesh for the
 * hero background. Sits behind the hero content (absolutely positioned inside
 * a `position: relative` hero section that clips it) and drifts slowly.
 *
 * The blooms are translucent amber (rgba) so they read on both the warm cream
 * "paper" background and the dark gray theme. Respects prefers-reduced-motion:
 * when set, the blobs render static in their base positions.
 */

// Each blob: base position, size, gradient, blur, and an independent drift
// keyframe set. Durations/delays differ per blob so they never sync up.
const BLOBS = [
  {
    className: 'w-[42rem] h-[42rem] -top-40 -left-32',
    background: 'radial-gradient(circle, rgba(255,138,0,0.22), transparent 60%)',
    blur: 'blur(70px)',
    animate: { x: [0, 50, 0], y: [0, 40, 0], scale: [1, 1.1, 1] },
    duration: 18,
    delay: 0,
  },
  {
    className: 'w-[38rem] h-[38rem] -top-24 -right-40',
    background: 'radial-gradient(circle, rgba(255,178,90,0.18), transparent 60%)',
    blur: 'blur(64px)',
    animate: { x: [0, -60, 0], y: [0, 50, 0], scale: [1, 1.12, 1] },
    duration: 21,
    delay: 1.5,
  },
  {
    className: 'w-[40rem] h-[40rem] -bottom-48 -left-24',
    background: 'radial-gradient(circle, rgba(255,138,0,0.16), transparent 60%)',
    blur: 'blur(72px)',
    animate: { x: [0, 45, 0], y: [0, -35, 0], scale: [1, 1.08, 1] },
    duration: 16,
    delay: 3,
  },
  {
    className: 'w-[34rem] h-[34rem] -bottom-40 -right-28',
    background: 'radial-gradient(circle, rgba(255,178,90,0.13), transparent 60%)',
    blur: 'blur(60px)',
    animate: { x: [0, -40, 0], y: [0, -50, 0], scale: [1, 1.1, 1] },
    duration: 22,
    delay: 2,
  },
];

export default function HeroMesh() {
  const reduceMotion = useReducedMotion();

  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 pointer-events-none overflow-hidden"
    >
      {BLOBS.map((blob, i) => (
        <motion.div
          key={i}
          className={`absolute rounded-full ${blob.className}`}
          style={{ background: blob.background, filter: blob.blur }}
          animate={reduceMotion ? undefined : blob.animate}
          transition={
            reduceMotion
              ? undefined
              : {
                  duration: blob.duration,
                  delay: blob.delay,
                  repeat: Infinity,
                  repeatType: 'mirror',
                  ease: 'easeInOut',
                }
          }
        />
      ))}
    </div>
  );
}
