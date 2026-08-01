import { motion } from 'framer-motion';

export default function BentoCard({ children, className = '', index = 0, span = '', hero = false }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: index * 0.06, ease: [0.25, 0.46, 0.45, 0.94] }}
      // Spring lift on hover, on the same editorial surface as Card.
      whileHover={{ y: -2, transition: { type: 'spring', stiffness: 400, damping: 28 } }}
      className={`card-rich shadow-editorial ring-1 ring-black/5 dark:ring-white/10 rounded-2xl relative overflow-hidden flex flex-col ${hero ? 'p-7' : 'p-6'} ${span} ${className}`}
    >
      {hero && (
        <span className="pointer-events-none absolute inset-x-0 top-0 h-[3px] bg-gradient-to-r from-primary-500 via-primary-400 to-primary-600" />
      )}
      {children}
    </motion.div>
  );
}
