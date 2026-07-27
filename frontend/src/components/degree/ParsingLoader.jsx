import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const STATUS_MESSAGES = [
  'Establishing connection to AI engine...',
  'Scanning document structure...',
  'Analyzing Lassonde School of Engineering requirements...',
  'Mapping EECS core credit buckets...',
  'Extracting completed course history...',
  'Identifying prerequisite chains...',
  'Cross-referencing degree requirements...',
  'Verifying credit allocations...',
  'Building your academic profile...',
  'Almost there — finalizing results...',
];

const MESSAGE_INTERVAL = 3500;

// Simulated progress: fast at first, slows as it approaches 95%
function useSimulatedProgress(active) {
  const [progress, setProgress] = useState(0);
  const raf = useRef(null);
  const start = useRef(null);

  useEffect(() => {
    if (!active) {
      setProgress(0);
      start.current = null;
      if (raf.current) cancelAnimationFrame(raf.current);
      return;
    }

    start.current = Date.now();

    function tick() {
      const elapsed = (Date.now() - start.current) / 1000;
      // Asymptotic curve: approaches 95 over ~60s, fast early
      const p = 95 * (1 - Math.exp(-elapsed / 20));
      setProgress(Math.min(p, 95));
      raf.current = requestAnimationFrame(tick);
    }

    raf.current = requestAnimationFrame(tick);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [active]);

  return progress;
}

export default function ParsingLoader({ visible, finishing }) {
  const [msgIndex, setMsgIndex] = useState(0);
  const progress = useSimulatedProgress(visible);

  // Cycle status messages
  useEffect(() => {
    if (!visible) { setMsgIndex(0); return; }
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % STATUS_MESSAGES.length);
    }, MESSAGE_INTERVAL);
    return () => clearInterval(interval);
  }, [visible]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
          className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-dark-950/80 backdrop-blur-2xl rounded-xl"
        >
          {/* Orbital ring */}
          <div className="relative w-28 h-28 mb-8">
            {/* Outer ring — slow spin */}
            <motion.div
              className="absolute inset-0 rounded-full border-2 border-primary-500/20"
              animate={{ rotate: 360 }}
              transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
            />
            {/* Middle ring — opposite spin */}
            <motion.div
              className="absolute inset-2 rounded-full border-2 border-dark-500/25"
              animate={{ rotate: -360 }}
              transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
            />
            {/* Inner ring — fast, gradient arc */}
            <motion.div
              className="absolute inset-4 rounded-full"
              style={{
                background: 'conic-gradient(from 0deg, transparent 60%, rgba(255,138,0,0.5) 80%, rgba(240,126,0,0.6) 95%, transparent 100%)',
              }}
              animate={{ rotate: 360 }}
              transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
            />
            {/* Center glow */}
            <div className="absolute inset-6 rounded-full bg-primary-500/15 flex items-center justify-center">
              <motion.div
                className="w-8 h-8 rounded-full bg-primary-500"
                animate={{ scale: [1, 1.15, 1], opacity: [0.7, 1, 0.7] }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              />
            </div>
            {/* Orbiting dot */}
            <motion.div
              className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2"
              animate={{ rotate: 360 }}
              transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
              style={{ transformOrigin: '50% calc(50% + 56px)' }}
            >
              <div className="w-2 h-2 rounded-full bg-primary-400" />
            </motion.div>
          </div>

          {/* Status message */}
          <div className="h-6 flex items-center justify-center mb-6 px-4">
            <AnimatePresence mode="wait">
              <motion.p
                key={msgIndex}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3 }}
                className="text-dark-300 text-sm text-center"
              >
                {finishing ? 'Parsing complete — loading your courses...' : STATUS_MESSAGES[msgIndex]}
              </motion.p>
            </AnimatePresence>
          </div>

          {/* Progress bar */}
          <div className="w-64 h-1.5 bg-dark-800 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-primary-500 rounded-full"
              animate={{ width: finishing ? '100%' : `${progress}%` }}
              transition={{ duration: finishing ? 0.4 : 0.3, ease: 'easeOut' }}
            />
          </div>

          {/* Percentage */}
          <p className="text-dark-500 text-xs mt-2 tabular-nums">
            {finishing ? '100' : Math.round(progress)}%
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
