import { motion, useReducedMotion } from 'framer-motion';

/** Shared page easing — matches the hero's authored reveal. */
const ease = [0.16, 1, 0.3, 1];

/**
 * Scroll-triggered masked word-reveal for section headings.
 *
 * Like the hero's `SplitWords`, but fires `whileInView` (once) instead of on
 * mount, so every heading down the page shares the hero's reveal language.
 * Words at index >= `accentFrom` receive the `text-gradient-warm` amber
 * gradient (the common trailing-accent-word heading pattern).
 */
export default function RevealText({
  text,
  as = 'h2',
  className = '',
  delay = 0,
  stagger = 0.05,
  accentFrom,
  once = true,
}) {
  const reduced = useReducedMotion();
  const Tag = as;

  const isAccent = (i) =>
    typeof accentFrom === 'number' && i >= accentFrom;

  // Reduced motion: plain text, accent gradient preserved, no animation.
  if (reduced) {
    if (typeof accentFrom !== 'number') {
      return <Tag className={className}>{text}</Tag>;
    }
    const words = text.split(' ');
    return (
      <Tag className={className}>
        {words.map((word, i) => (
          <span
            key={`${word}-${i}`}
            className={isAccent(i) ? 'text-gradient-warm' : undefined}
          >
            {word}
            {i < words.length - 1 ? ' ' : ''}
          </span>
        ))}
      </Tag>
    );
  }

  return (
    <Tag className={className}>
      {text.split(' ').map((word, i) => (
        <span
          key={`${word}-${i}`}
          className="inline-block overflow-hidden align-bottom pb-[0.1em] -mb-[0.1em]"
        >
          <motion.span
            className={`inline-block will-change-transform${
              isAccent(i) ? ' text-gradient-warm' : ''
            }`}
            initial={{ y: '115%' }}
            whileInView={{ y: 0 }}
            viewport={{ once, margin: '-60px' }}
            transition={{ duration: 0.7, delay: delay + i * stagger, ease }}
          >
            {word}
            {' '}
          </motion.span>
        </span>
      ))}
    </Tag>
  );
}
