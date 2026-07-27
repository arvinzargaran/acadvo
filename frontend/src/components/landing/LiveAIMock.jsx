import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';

const ease = [0.16, 1, 0.3, 1];

// The scripted conversation the mock plays back on a loop.
const CONVERSATION = [
  { role: 'user', text: 'What should I take next semester?' },
  {
    role: 'ai',
    text:
      'Based on your progress, take STAT 2040 — it unlocks 4 upper-year courses you still need. You’ve also got room for one elective. Want picks for your career goal?',
  },
  { role: 'user', text: 'Yes — I’m aiming for product management.' },
  {
    role: 'ai',
    text:
      'Then add BUS 2090 (Product Strategy). It pairs with your CS track and reads strongly on a PM résumé.',
  },
];

const TYPE_SPEED = 18; // ms per character
const TYPING_DELAY = 900; // typing indicator duration
const PAUSE_AFTER_AI = 700; // beat before the next user turn
const HOLD_END = 2500; // hold the full convo before resetting

// ─── Presentational bubbles ──────────────────────────────────────────────────

function UserBubble({ text }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed bg-primary-500/15 border border-primary-500/30 text-dark-100">
        {text}
      </div>
    </div>
  );
}

function AIBubble({ children }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed bg-dark-900/40 border border-dark-600 text-gray-300">
        <span className="block text-[10px] text-primary-700 font-semibold mb-1">Acadvo AI</span>
        {children}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <AIBubble>
      <span className="flex items-center gap-1 py-0.5">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-dark-400"
            animate={{ y: [0, -3, 0], opacity: [0.4, 1, 0.4] }}
            transition={{
              duration: 0.9,
              repeat: Infinity,
              ease: 'easeInOut',
              delay: i * 0.15,
            }}
          />
        ))}
      </span>
    </AIBubble>
  );
}

const bubbleMotion = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, ease } },
  exit: { opacity: 0, transition: { duration: 0.2 } },
};

// ─── Card shell (shared by live + static variants) ───────────────────────────

function Shell({ children }) {
  return (
    <div className="relative rounded-2xl border border-dark-600 card-rich shadow-editorial overflow-hidden">
      {/* Window chrome */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-dark-600 bg-dark-900/60">
        <div className="w-3 h-3 rounded-full bg-dark-500/60" />
        <div className="w-3 h-3 rounded-full bg-dark-500/60" />
        <div className="w-3 h-3 rounded-full bg-dark-500/60" />
        <span className="mx-auto text-xs text-dark-400">acadvo — AI advisor</span>
      </div>

      {/* Chat body — min height keeps the card from jumping as messages appear */}
      <div className="p-4 flex flex-col gap-3 min-h-[300px]">{children}</div>

      {/* Fake input row */}
      <div className="px-4 pb-4">
        <div className="flex items-center gap-2 rounded-xl border border-dark-600 bg-dark-900/30 px-3 py-2">
          <span className="text-xs text-dark-400 flex-1">Ask anything about your degree...</span>
          <div className="w-5 h-5 rounded-full bg-primary-600 flex items-center justify-center">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3 text-white">
              <path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Static (reduced-motion) variant ─────────────────────────────────────────

function StaticMock() {
  return (
    <Shell>
      {CONVERSATION.map((msg, i) =>
        msg.role === 'user' ? (
          <UserBubble key={i} text={msg.text} />
        ) : (
          <AIBubble key={i}>{msg.text}</AIBubble>
        ),
      )}
    </Shell>
  );
}

// ─── Live (animated) variant ─────────────────────────────────────────────────

// Step machine phases:
//  'user'   — reveal user message at index `msg`
//  'typing' — show the typing indicator before an AI reply
//  'ai'     — typewriter the AI reply at index `msg`
//  'hold'   — full convo shown, waiting to reset
function LiveMock() {
  // Messages already fully committed to the transcript.
  const [committed, setCommitted] = useState([]);
  // Current phase + which conversation index it targets.
  const [phase, setPhase] = useState('user');
  const [index, setIndex] = useState(0);
  // Text currently being typed out for an AI reply.
  const [typed, setTyped] = useState('');

  const timers = useRef([]);

  // Register a timeout that is guaranteed to be cleared on unmount/re-run.
  const schedule = (fn, ms) => {
    const id = setTimeout(fn, ms);
    timers.current.push(id);
    return id;
  };

  useEffect(() => {
    const msg = CONVERSATION[index];

    if (phase === 'user') {
      // Commit the user message, then advance to the AI typing indicator.
      // Guard against duplicate appends (React 18 StrictMode double-invokes effects in dev).
      setCommitted((prev) =>
        prev.some((m) => m.key === index) ? prev : [...prev, { ...msg, key: index }],
      );
      schedule(() => setPhase('typing'), 550);
      return undefined;
    }

    if (phase === 'typing') {
      setTyped('');
      schedule(() => setPhase('ai'), TYPING_DELAY);
      return undefined;
    }

    if (phase === 'ai') {
      // Typewriter the AI response character by character.
      let charIndex = 0;
      const interval = setInterval(() => {
        charIndex += 1;
        setTyped(msg.text.slice(0, charIndex));
        if (charIndex >= msg.text.length) {
          clearInterval(interval);
          // Commit the finished AI message and clear the live-typing buffer.
          schedule(() => {
            setCommitted((prev) =>
              prev.some((m) => m.key === index) ? prev : [...prev, { ...msg, key: index }],
            );
            setTyped('');
            const next = index + 1;
            if (next < CONVERSATION.length) {
              schedule(() => {
                setIndex(next);
                setPhase('user');
              }, PAUSE_AFTER_AI);
            } else {
              setPhase('hold');
            }
          }, 60);
        }
      }, TYPE_SPEED);
      timers.current.push(interval);
      return () => clearInterval(interval);
    }

    if (phase === 'hold') {
      // Reset back to an empty transcript and loop.
      schedule(() => {
        setCommitted([]);
        setTyped('');
        setIndex(0);
        setPhase('user');
      }, HOLD_END);
      return undefined;
    }

    return undefined;
  }, [phase, index]);

  // Global cleanup — clears every pending timeout/interval on unmount.
  useEffect(
    () => () => {
      timers.current.forEach((id) => {
        clearTimeout(id);
        clearInterval(id);
      });
      timers.current = [];
    },
    [],
  );

  return (
    <Shell>
      <AnimatePresence initial={false}>
        {committed.map((msg) => (
          <motion.div key={`c-${msg.key}-${msg.role}`} {...bubbleMotion}>
            {msg.role === 'user' ? (
              <UserBubble text={msg.text} />
            ) : (
              <AIBubble>{msg.text}</AIBubble>
            )}
          </motion.div>
        ))}

        {phase === 'typing' && (
          <motion.div key="typing" {...bubbleMotion}>
            <TypingIndicator />
          </motion.div>
        )}

        {phase === 'ai' && (
          <motion.div key="typing-out" {...bubbleMotion}>
            <AIBubble>
              {typed}
              <motion.span
                aria-hidden="true"
                className="inline-block w-[2px] h-3 ml-0.5 -mb-0.5 bg-primary-600 align-middle"
                animate={{ opacity: [1, 0] }}
                transition={{ duration: 0.6, repeat: Infinity, ease: 'linear' }}
              />
            </AIBubble>
          </motion.div>
        )}
      </AnimatePresence>
    </Shell>
  );
}

export default function LiveAIMock() {
  const reduced = useReducedMotion();
  return reduced ? <StaticMock /> : <LiveMock />;
}
