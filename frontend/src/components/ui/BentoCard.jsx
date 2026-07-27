import { motion } from 'framer-motion';

export default function BentoCard({ children, className = '', index = 0, span = '' }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: index * 0.08, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={{ y: -2 }}
      className={`bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl p-6 shadow-sm transition-all duration-300 ${span} ${className}`}
    >
      {children}
    </motion.div>
  );
}
