import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ── Category config ──────────────────────────────────────────────

const CATEGORIES = {
  gpa:      { label: 'GPA Strategy',      color: 'emerald', icon: 'M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z' },
  schedule: { label: 'Schedule Alert',     color: 'amber',   icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  career:   { label: 'Career Move',        color: 'indigo',  icon: 'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
  project:  { label: 'Project Insight',    color: 'indigo',  icon: 'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4' },
  degree:   { label: 'Degree Progress',    color: 'emerald', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  risk:     { label: 'Heads Up',           color: 'amber',   icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.832c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z' },
};

const COLOR_MAP = {
  emerald: { tag: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20', accent: 'text-emerald-400', dot: 'bg-emerald-400', glow: 'shadow-emerald-500/10' },
  amber:   { tag: 'bg-amber-500/15 text-amber-400 border-amber-500/20',     accent: 'text-amber-400',   dot: 'bg-amber-400',   glow: 'shadow-amber-500/10' },
  indigo:  { tag: 'bg-primary-500/15 text-primary-400 border-primary-500/20',   accent: 'text-primary-400',  dot: 'bg-primary-400',  glow: 'shadow-primary-500/10' },
};

// ── Insight generator ────────────────────────────────────────────

function generateInsights({ summary, courses, projects, events }) {
  const insights = [];
  const now = new Date();

  // ─ GPA strategy ─
  if (summary?.cumulative_gpa != null) {
    const gpa = summary.cumulative_gpa;
    const inProgress = courses?.filter(c => c.status === 'in_progress') || [];
    if (gpa < 3.0 && inProgress.length > 0) {
      const course = inProgress[0];
      insights.push({
        id: 'gpa-boost',
        category: 'gpa',
        priority: 1,
        headline: `Road to ${(gpa + 0.5).toFixed(1)}`,
        body: `Finishing strong in ${course.course_code} this term could lift your cumulative GPA past ${(gpa + 0.3).toFixed(1)} — keep the momentum going.`,
        action: { label: 'View Degree', href: '/degree' },
      });
    } else if (gpa >= 3.0) {
      insights.push({
        id: 'gpa-maintain',
        category: 'gpa',
        priority: 3,
        headline: 'GPA on Track',
        body: `Your ${gpa.toFixed(2)} cumulative puts you in a strong position. Consistency this term secures scholarship and co-op eligibility.`,
        action: { label: 'View Degree', href: '/degree' },
      });
    }
  }

  // ─ At-risk buckets ─
  const atRisk = summary?.buckets?.filter(b => b.at_risk) || [];
  if (atRisk.length > 0) {
    const names = atRisk.slice(0, 2).map(b => b.bucket_name).join(' and ');
    insights.push({
      id: 'bucket-risk',
      category: 'degree',
      priority: 1,
      headline: 'Degree Requirements Gap',
      body: `Your ${names} bucket${atRisk.length > 1 ? 's need' : ' needs'} attention — plan courses for next term to stay on track for graduation.`,
      action: { label: 'Plan Courses', href: '/degree' },
    });
  }

  // ─ Urgent deadlines ─
  const urgentDeadlines = (events || []).filter(e => {
    if (!e.is_hard_deadline) return false;
    const days = Math.ceil((new Date(e.event_date) - now) / (1000 * 60 * 60 * 24));
    return days >= 0 && days <= 7;
  });
  if (urgentDeadlines.length > 0) {
    const d = urgentDeadlines[0];
    const days = Math.ceil((new Date(d.event_date) - now) / (1000 * 60 * 60 * 24));
    insights.push({
      id: 'urgent-deadline',
      category: 'schedule',
      priority: 0,
      headline: days === 0 ? 'Due Today' : days === 1 ? 'Due Tomorrow' : `${days} Days Left`,
      body: `"${d.title}" is coming up fast. Block time today to make sure it's ready.`,
      action: { label: 'View Schedule', href: '/schedule' },
    });
  }

  // ─ Project strategy ─
  if (projects && projects.length > 0) {
    const techCounts = {};
    projects.forEach(p => {
      (p.tech_stack || '').split(',').map(t => t.trim().toLowerCase()).filter(Boolean).forEach(t => {
        techCounts[t] = (techCounts[t] || 0) + 1;
      });
    });
    const topTech = Object.entries(techCounts).sort((a, b) => b[1] - a[1])[0];
    const notDeployed = projects.filter(p => p.status !== 'deployed' && p.status !== 'interview_ready');

    if (topTech && notDeployed.length > 0) {
      insights.push({
        id: 'project-strategy',
        category: 'project',
        priority: 2,
        headline: 'Portfolio Boost',
        body: `You have ${topTech[1]} ${topTech[0]} project${topTech[1] > 1 ? 's' : ''}. Deploying "${notDeployed[0].name}" would strengthen your Co-op readiness score.`,
        action: { label: 'View Projects', href: '/projects' },
      });
    }
  } else {
    insights.push({
      id: 'no-projects',
      category: 'career',
      priority: 2,
      headline: 'Start Building',
      body: 'A portfolio project is the fastest way to stand out in co-op applications. Even a small full-stack app makes a difference.',
      action: { label: 'Add Project', href: '/projects' },
    });
  }

  // ─ No courses in progress ─
  const inProgress = courses?.filter(c => c.status === 'in_progress') || [];
  if (courses?.length > 0 && inProgress.length === 0) {
    insights.push({
      id: 'update-courses',
      category: 'schedule',
      priority: 2,
      headline: 'Course Status Stale',
      body: 'None of your courses are marked "in progress." Update them so your dashboard reflects reality.',
      action: { label: 'Update Courses', href: '/degree' },
    });
  }

  // ─ Overdue milestones ─
  const overdue = [];
  projects?.forEach(p => {
    p.milestones?.forEach(m => {
      if (m.target_date && m.status !== 'complete') {
        const days = Math.ceil((new Date(m.target_date) - now) / (1000 * 60 * 60 * 24));
        if (days < 0) overdue.push({ ...m, projectName: p.name, daysOverdue: -days });
      }
    });
  });
  if (overdue.length > 0) {
    const worst = overdue.sort((a, b) => b.daysOverdue - a.daysOverdue)[0];
    insights.push({
      id: 'overdue-milestone',
      category: 'risk',
      priority: 1,
      headline: 'Milestone Overdue',
      body: `"${worst.title}" on ${worst.projectName} is ${worst.daysOverdue} day${worst.daysOverdue > 1 ? 's' : ''} past due. Reschedule or mark complete.`,
      action: { label: 'View Projects', href: '/projects' },
    });
  }

  // ─ Career targets ─
  const hasTargets = (events || []).some(e => e.event_type === 'application' || e.event_type === 'interview');
  if (!hasTargets && projects?.length > 0) {
    insights.push({
      id: 'career-targets',
      category: 'career',
      priority: 3,
      headline: 'Set Your Sights',
      body: 'Adding target companies helps your AI advisor tailor project and course recommendations to your goals.',
      action: { label: 'Add Targets', href: '/career' },
    });
  }

  return insights.sort((a, b) => a.priority - b.priority);
}

// ── Convert server suggestions into insight format ───────────────

function mapServerSuggestions(suggestions) {
  return (suggestions || []).map(s => {
    let category = 'career';
    if (s.suggestion_type === 'course') category = 'gpa';
    else if (s.suggestion_type === 'schedule') category = 'schedule';
    else if (s.suggestion_type === 'project') category = 'project';
    else if (s.suggestion_type === 'risk_flag') category = 'risk';

    return {
      id: `server-${s.id}`,
      serverId: s.id,
      category,
      priority: s.severity === 'high' ? 0 : s.severity === 'medium' ? 1 : 2,
      headline: CATEGORIES[category]?.label || 'Insight',
      body: s.content,
      action: null,
      isServer: true,
    };
  });
}

// ── Auto-cycle interval ──────────────────────────────────────────

const CYCLE_INTERVAL = 6000;

// ── Component ────────────────────────────────────────────────────

export default function SmartInsightsFeed({ summary, courses, projects, events, suggestions, onAccept, onDismiss }) {
  const generated = generateInsights({ summary, courses, projects, events });
  const server = mapServerSuggestions(suggestions);
  const allInsights = [...server, ...generated].sort((a, b) => a.priority - b.priority);

  const [activeIndex, setActiveIndex] = useState(0);
  const [direction, setDirection] = useState(1);
  const [paused, setPaused] = useState(false);
  const manualCooldown = useRef(0);

  const count = allInsights.length;

  const advance = useCallback((dir = 1) => {
    if (count <= 1) return;
    setDirection(dir);
    setActiveIndex(i => (i + dir + count) % count);
  }, [count]);

  const manualAdvance = useCallback((dir) => {
    advance(dir);
    manualCooldown.current = Date.now() + CYCLE_INTERVAL * 2;
  }, [advance]);

  const goToSlide = useCallback((i) => {
    setDirection(i > activeIndex ? 1 : -1);
    setActiveIndex(i);
    manualCooldown.current = Date.now() + CYCLE_INTERVAL * 2;
  }, [activeIndex]);

  // Auto-cycle (respects manual cooldown)
  useEffect(() => {
    if (count <= 1 || paused) return;
    const timer = setInterval(() => {
      if (Date.now() >= manualCooldown.current) {
        advance(1);
      }
    }, CYCLE_INTERVAL);
    return () => clearInterval(timer);
  }, [count, paused, advance]);

  if (count === 0) {
    return (
      <div>
        <Header count={0} />
        <p className="text-dark-500 text-sm mt-2">Everything looks good — no insights right now.</p>
      </div>
    );
  }

  const insight = allInsights[activeIndex % count];
  const cat = CATEGORIES[insight.category] || CATEGORIES.career;
  const colors = COLOR_MAP[cat.color];

  return (
    <div
      className="h-full flex flex-col"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <Header count={count} activeIndex={activeIndex % count} />

      {/* Featured insight */}
      <div className="flex-1 relative mt-3 min-h-[130px]">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={insight.id}
            custom={direction}
            initial={{ opacity: 0, x: direction > 0 ? 30 : -30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: direction > 0 ? -30 : 30 }}
            transition={{ duration: 0.28, ease: 'easeInOut' }}
            className="flex flex-col h-full pb-2"
          >
            {/* Category tag */}
            <div className="flex items-center gap-2 mb-2">
              <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full border ${colors.tag}`}>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={cat.icon} />
                </svg>
                {cat.label}
              </span>
            </div>

            {/* Headline */}
            <p className={`font-bold text-base ${colors.accent} mb-1`}>{insight.headline}</p>

            {/* Body */}
            <p className="text-dark-300 text-sm leading-relaxed flex-1">{insight.body}</p>

            {/* Actions */}
            <div className="flex items-center gap-2 mt-3">
              {insight.action && (
                <a
                  href={insight.action.href}
                  className={`text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors ${colors.tag} hover:bg-white/10`}
                >
                  {insight.action.label}
                </a>
              )}
              {insight.isServer && (
                <>
                  <button
                    onClick={() => onAccept?.(insight.serverId)}
                    className="text-xs font-medium px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
                  >
                    Add to Plan
                  </button>
                  <button
                    onClick={() => onDismiss?.(insight.serverId)}
                    className="text-xs font-medium px-3 py-1.5 rounded-lg bg-white/5 text-dark-400 border border-white/10 hover:bg-white/10 hover:text-dark-300 transition-colors"
                  >
                    Dismiss
                  </button>
                </>
              )}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Pagination dots + arrows */}
      {count > 1 && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/5">
          <button
            onClick={() => manualAdvance(-1)}
            className="text-dark-500 hover:text-white transition-colors p-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="flex items-center gap-1.5">
            {allInsights.map((_, i) => (
              <button
                key={i}
                onClick={() => goToSlide(i)}
                className={`rounded-full transition-all duration-300 ${
                  i === activeIndex % count
                    ? `w-5 h-1.5 ${colors.dot.replace('bg-', 'bg-')}`
                    : 'w-1.5 h-1.5 bg-dark-600 hover:bg-dark-500'
                }`}
              />
            ))}
          </div>
          <button
            onClick={() => manualAdvance(1)}
            className="text-dark-500 hover:text-white transition-colors p-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}

function Header({ count }) {
  return (
    <div className="flex items-center gap-2">
      <svg className="w-4 h-4 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
      <h3 className="text-white font-semibold">Smart Insights</h3>
      {count > 0 && <span className="text-dark-500 text-xs">{count} insight{count !== 1 ? 's' : ''}</span>}
    </div>
  );
}
