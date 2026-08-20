import { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';

const TOUR_STEPS = [
  {
    title: 'Welcome to Acadvo!',
    description: 'Your AI-powered academic advisor. Let me show you around.',
    position: 'center',
  },
  {
    title: 'Dashboard',
    description: 'Your home base — see GPA, credits, deadlines, and smart alerts at a glance.',
    selector: '[data-tour="dashboard-grid"]',
    position: 'bottom',
  },
  {
    title: 'AI Chat Assistant',
    description: 'Click the chat bubble anytime to ask your AI advisor questions, get course recommendations, or build your career plan.',
    selector: '[data-tour="chat-widget"]',
    position: 'top-left',
  },
  {
    title: 'Navigation',
    description: 'Use the sidebar to access Degree tracking, Course Advisor, Projects, Career planning, and DSA Prep.',
    selector: '[data-tour="sidebar-nav"]',
    position: 'right',
  },
  {
    title: 'You\'re all set!',
    description: 'Start by importing your degree checklist on the Degree page, or ask the AI chat for help getting started.',
    position: 'center',
  },
];

const STORAGE_KEY = 'acadvo_tour_complete';

export default function OnboardingTour() {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(false);
  const [tooltipStyle, setTooltipStyle] = useState({ position: 'fixed', opacity: 0 });
  const tooltipRef = useRef(null);

  useEffect(() => {
    const done = localStorage.getItem(STORAGE_KEY);
    if (!done) {
      // Delay slightly so DOM is ready
      const timer = setTimeout(() => setVisible(true), 1000);
      return () => clearTimeout(timer);
    }
  }, []);

  // Position the tooltip near its target, but always keep it fully on-screen.
  // Anchors can point off-screen (e.g. the "bottom" of a full-height grid), so
  // we compute a top-left corner and then clamp it into the viewport.
  const positionTooltip = useCallback(() => {
    const current = TOUR_STEPS[step];
    const tip = tooltipRef.current;
    if (!tip) return;

    const tipW = tip.offsetWidth || 320;
    const tipH = tip.offsetHeight || 160;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const margin = 16;

    const centered = () =>
      setTooltipStyle({
        position: 'fixed',
        top: `${Math.max(margin, (vh - tipH) / 2)}px`,
        left: `${Math.max(margin, (vw - tipW) / 2)}px`,
        opacity: 1,
      });

    const el = current.selector ? document.querySelector(current.selector) : null;
    if (!current.selector || current.position === 'center' || !el) {
      centered();
      return;
    }

    const rect = el.getBoundingClientRect();
    let top;
    let left;

    if (current.position === 'top-left') {
      top = rect.top - 12 - tipH;
      left = rect.left;
    } else if (current.position === 'right') {
      top = rect.top + rect.height / 2 - tipH / 2;
      left = rect.right + 12;
    } else {
      // 'bottom' (default): sit just under the target's visible top edge so the
      // tooltip stays in view even when the target extends past the fold.
      top = Math.min(rect.bottom, rect.top + 120) + 12;
      left = rect.left + rect.width / 2 - tipW / 2;
    }

    // Clamp fully inside the viewport.
    left = Math.min(Math.max(margin, left), vw - tipW - margin);
    top = Math.min(Math.max(margin, top), vh - tipH - margin);

    setTooltipStyle({ position: 'fixed', top: `${top}px`, left: `${left}px`, opacity: 1 });
  }, [step]);

  useLayoutEffect(() => {
    if (!visible) return;
    positionTooltip();
    window.addEventListener('resize', positionTooltip);
    window.addEventListener('scroll', positionTooltip, true);
    return () => {
      window.removeEventListener('resize', positionTooltip);
      window.removeEventListener('scroll', positionTooltip, true);
    };
  }, [visible, positionTooltip]);

  const finish = () => {
    localStorage.setItem(STORAGE_KEY, 'true');
    setVisible(false);
  };

  const next = () => {
    if (step >= TOUR_STEPS.length - 1) {
      finish();
    } else {
      setStep(s => s + 1);
    }
  };

  if (!visible) return null;

  const current = TOUR_STEPS[step];

  return (
    <>
      {/* Overlay */}
      {/* Decorative; the tooltip's Skip and Next buttons are the keyboard path out. */}
      <div aria-hidden="true" className="fixed inset-0 bg-black/40 z-[100]" onClick={finish} />

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        style={tooltipStyle}
        className="z-[101] w-80 bg-dark-800 border border-dark-600 rounded-xl p-5 shadow-2xl"
      >
        <h3 className="text-dark-50 font-semibold text-sm">{current.title}</h3>
        <p className="text-dark-300 text-sm mt-1.5">{current.description}</p>
        <div className="flex items-center justify-between mt-4">
          <div className="flex gap-1">
            {TOUR_STEPS.map((_, i) => (
              <div
                key={i}
                className={`w-2 h-2 rounded-full transition-colors ${i === step ? 'bg-primary-500' : 'bg-dark-600'}`}
              />
            ))}
          </div>
          <div className="flex gap-2">
            <button
              onClick={finish}
              className="text-dark-400 hover:text-dark-50 text-xs transition-colors"
            >
              Skip
            </button>
            <button
              onClick={next}
              className="px-3 py-1 bg-primary-600 hover:bg-primary-700 text-white text-xs rounded-lg transition-all"
            >
              {step >= TOUR_STEPS.length - 1 ? 'Get Started' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
