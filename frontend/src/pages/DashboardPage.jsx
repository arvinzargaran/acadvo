import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import BentoCard from '../components/ui/BentoCard';
import ReadinessScore from '../components/dashboard/ReadinessScore';
import GPACalculator from '../components/dashboard/GPACalculator';
import CreditProgress from '../components/dashboard/CreditProgress';
import SmartInsightsFeed from '../components/dashboard/SmartInsightsFeed';
import CurrentCourses from '../components/dashboard/CurrentCourses';
import WeeklyCheckin from '../components/dashboard/WeeklyCheckin';
import GettingStarted from '../components/dashboard/GettingStarted';
import { getDegreeSummary, listCourses } from '../api/degree';
import { listProjects } from '../api/projects';
import { listTimelineEvents, listCareerTargets } from '../api/career';
import { listSuggestions, updateSuggestion } from '../api/suggestions';
import { getStudyStats } from '../api/study';
import toast from 'react-hot-toast';
import Skeleton from '../components/ui/Skeleton';

export default function DashboardPage() {
  const { user } = useAuth();
  const [degreeSummary, setDegreeSummary] = useState(null);
  const [courses, setCourses] = useState([]);
  const [projects, setProjects] = useState([]);
  const [events, setEvents] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [studyStats, setStudyStats] = useState(null);
  const [careerTargets, setCareerTargets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [summaryRes, coursesRes, projectsRes, eventsRes, suggestionsRes, studyRes, targetsRes] = await Promise.all([
          getDegreeSummary().catch(() => null),
          listCourses().catch(() => []),
          listProjects().catch(() => []),
          listTimelineEvents().catch(() => []),
          listSuggestions().catch(() => []),
          getStudyStats().catch(() => null),
          listCareerTargets().catch(() => []),
        ]);
        setDegreeSummary(summaryRes?.data);
        setCourses(coursesRes?.data || []);
        setProjects(projectsRes?.data || []);
        setEvents(eventsRes?.data || []);
        setSuggestions(suggestionsRes?.data || []);
        setStudyStats(studyRes?.data || null);
        setCareerTargets(targetsRes?.data || []);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // ── First-run detection ─────────────────────────────────────────
  // Derive per-step completion from data the page already fetched.
  const hasDegree = !!(degreeSummary && (degreeSummary.total_credits_completed > 0 || degreeSummary.buckets?.length > 0));
  const hasCourses = courses.length > 0;
  const hasProjects = projects.length > 0;
  const hasCareer = careerTargets.length > 0 || events.length > 0;
  const isNewAccount = !hasDegree && !hasCourses && !hasProjects && !hasCareer;

  const handleAccept = async (id) => {
    await updateSuggestion(id, { accepted: true });
    setSuggestions(prev => prev.filter(s => s.id !== id));
    toast.success('Applied suggestion to your plan!');
  };

  const handleDismiss = async (id) => {
    await updateSuggestion(id, { accepted: false });
    setSuggestions(prev => prev.filter(s => s.id !== id));
    toast('Suggestion dismissed', { icon: '👋' });
  };

  if (loading) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="min-h-full">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mb-10"
      >
        <h1 className="text-4xl sm:text-5xl font-bold text-dark-50 tracking-tight">
          Welcome back, {user?.full_name?.split(' ')[0]}
        </h1>
        <p className="text-gray-500 dark:text-dark-400 mt-2 text-lg">Here's your academic overview</p>
      </motion.div>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6" data-tour="dashboard-grid">

        {/* First-run "Getting started" checklist (full width, top of grid) */}
        {isNewAccount && (
          <GettingStarted
            hasDegree={hasDegree}
            hasProjects={hasProjects}
            hasCareer={hasCareer}
            className="md:col-span-2 lg:col-span-4"
          />
        )}

        {/* Hero — Co-op Readiness (2x2) */}
        <BentoCard index={0} span="md:col-span-2 md:row-span-2">
          <ReadinessScore bento />
        </BentoCard>

        {/* GPA (1x1) */}
        <BentoCard index={1}>
          <GPACalculator compact bento />
        </BentoCard>

        {/* Credits (1x1) */}
        <BentoCard index={2}>
          <CreditProgress summary={degreeSummary} bento />
        </BentoCard>

        {/* Study Streak (1x1) */}
        <BentoCard index={7}>
          <div className="flex flex-col h-full p-1 rounded-xl">
            <h3 className="text-gray-900 dark:text-white font-semibold mb-3 flex items-center gap-2">
              <svg className="w-4 h-4 text-primary-600 dark:text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Focus Timer
            </h3>
            {studyStats && (
              <div className="flex-1 flex flex-col justify-center items-center">
                <div className="text-4xl font-bold tabular-nums text-gray-900 dark:text-white leading-none mb-1">
                  {studyStats.current_streak} <span className="text-sm font-normal text-gray-500 dark:text-dark-400">days</span>
                </div>
                <p className="text-xs text-gray-600 dark:text-dark-300">Today: {studyStats.today_minutes}m</p>
              </div>
            )}
            <Link to="/study" className="mt-4 w-full block text-center bg-gray-100 dark:bg-dark-700 hover:bg-gray-200 dark:hover:bg-dark-600 text-gray-900 dark:text-white text-xs py-2 rounded-lg transition">Start Session</Link>
          </div>
        </BentoCard>

        {/* Upcoming Milestones (2x2) */}
        <BentoCard index={3} span="md:col-span-2 md:row-span-2">
          <MilestonesCombo events={events} projects={projects} />
        </BentoCard>

        {/* Smart Insights (2x1) */}
        <BentoCard index={4} span="md:col-span-2">
          <SmartInsightsFeed
            summary={degreeSummary}
            courses={courses}
            projects={projects}
            events={events}
            suggestions={suggestions}
            onAccept={handleAccept}
            onDismiss={handleDismiss}
          />
        </BentoCard>

        {/* Weekly Check-in (2x1) */}
        <BentoCard index={5} span="md:col-span-2">
          <WeeklyCheckin bento />
        </BentoCard>

        {/* Current Courses (2x1) */}
        <BentoCard index={6} span="md:col-span-2">
          <CurrentCourses courses={courses} bento />
        </BentoCard>
      </div>
    </div>
  );
}

// ── Loading Skeleton ─────────────────────────────────────────────
// Widget-shaped placeholders that mirror the bento grid layout so the
// dashboard "settles into place" instead of flashing blank space.

function SkeletonCard({ span = '', children }) {
  return (
    <div className={`bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl p-6 shadow-sm ${span}`}>
      {children}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="min-h-full">
      {/* Header */}
      <div className="mb-10">
        <Skeleton className="h-11 w-72 max-w-full mb-3 rounded-xl" />
        <Skeleton className="h-5 w-56 max-w-full" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Hero — Readiness (2x2) */}
        <SkeletonCard span="md:col-span-2 md:row-span-2">
          <Skeleton className="h-3 w-32 mb-6" />
          <div className="flex items-center gap-8">
            <Skeleton className="h-40 w-40 rounded-full flex-shrink-0" />
            <div className="flex-1 space-y-4">
              <Skeleton className="h-5 w-40" />
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-1.5 w-full rounded-full" />
                </div>
              ))}
            </div>
          </div>
        </SkeletonCard>

        {/* GPA (1x1) */}
        <SkeletonCard>
          <Skeleton className="h-4 w-20 mb-4" />
          <Skeleton className="h-10 w-24 mb-3" />
          <Skeleton className="h-2 w-full rounded-full" />
        </SkeletonCard>

        {/* Credits (1x1) */}
        <SkeletonCard>
          <Skeleton className="h-4 w-28 mb-4" />
          <div className="flex items-center gap-4">
            <Skeleton className="h-20 w-20 rounded-full flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-3 w-20" />
            </div>
          </div>
        </SkeletonCard>

        {/* Focus Timer (1x1) */}
        <SkeletonCard>
          <Skeleton className="h-4 w-24 mb-4" />
          <div className="flex flex-col items-center gap-2 py-2">
            <Skeleton className="h-10 w-20" />
            <Skeleton className="h-3 w-16" />
          </div>
          <Skeleton className="h-8 w-full rounded-lg mt-4" />
        </SkeletonCard>

        {/* Upcoming Milestones (2x2) */}
        <SkeletonCard span="md:col-span-2 md:row-span-2">
          <Skeleton className="h-4 w-40 mb-4" />
          <div className="space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-14 w-full rounded-xl" />
            ))}
          </div>
        </SkeletonCard>

        {/* Smart Insights (2x1) */}
        <SkeletonCard span="md:col-span-2">
          <Skeleton className="h-4 w-32 mb-4" />
          <div className="space-y-3">
            <Skeleton className="h-16 w-full rounded-xl" />
            <Skeleton className="h-16 w-full rounded-xl" />
          </div>
        </SkeletonCard>

        {/* Weekly Check-in (2x1) */}
        <SkeletonCard span="md:col-span-2">
          <Skeleton className="h-4 w-32 mb-4" />
          <Skeleton className="h-3 w-full mb-2" />
          <Skeleton className="h-3 w-5/6 mb-2" />
          <Skeleton className="h-3 w-2/3" />
        </SkeletonCard>

        {/* Current Courses (2x1) */}
        <SkeletonCard span="md:col-span-2">
          <Skeleton className="h-4 w-36 mb-4" />
          <div className="grid grid-cols-2 gap-3">
            <Skeleton className="h-12 w-full rounded-xl" />
            <Skeleton className="h-12 w-full rounded-xl" />
          </div>
        </SkeletonCard>
      </div>
    </div>
  );
}

// ── Combined Milestones Card ─────────────────────────────────────

function MilestonesCombo({ events, projects }) {
  const hardDeadlines = events
    ?.filter(e => e.is_hard_deadline && e.event_date)
    .sort((a, b) => new Date(a.event_date) - new Date(b.event_date))
    .slice(0, 4) || [];

  const milestones = [];
  projects?.forEach(p => {
    p.milestones
      ?.filter(m => m.status !== 'complete' && m.target_date)
      .slice(0, 2)
      .forEach(m => milestones.push({ ...m, projectName: p.name }));
  });
  milestones.sort((a, b) => new Date(a.target_date) - new Date(b.target_date));

  function daysUntil(dateStr) {
    return Math.ceil((new Date(dateStr) - new Date()) / (1000 * 60 * 60 * 24));
  }

  function daysBadge(days) {
    if (days < 0) return { text: 'Overdue', cls: 'bg-red-500/20 text-red-500 dark:text-red-400' };
    if (days === 0) return { text: 'Today', cls: 'bg-red-500/20 text-red-500 dark:text-red-400' };
    if (days === 1) return { text: 'Tomorrow', cls: 'bg-amber-500/20 text-amber-600 dark:text-amber-400' };
    if (days <= 7) return { text: `${days}d`, cls: 'bg-amber-500/20 text-amber-600 dark:text-amber-400' };
    return { text: `${days}d`, cls: 'bg-gray-100 dark:bg-dark-700 text-gray-600 dark:text-dark-300' };
  }

  return (
    <div className="h-full flex flex-col">
      <h3 className="text-gray-900 dark:text-white font-semibold mb-4 flex items-center gap-2">
        <svg className="w-4 h-4 text-primary-600 dark:text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        Upcoming Milestones
      </h3>

      <div className="space-y-2 flex-1 overflow-y-auto">
        {hardDeadlines.length === 0 && milestones.length === 0 && (
          <div className="bg-gray-50/80 dark:bg-dark-800/80 border border-gray-200 dark:border-dark-700/50 rounded-xl p-6 text-center mt-4">
            <div className="flex items-center justify-center w-16 h-16 mx-auto mb-4 bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 rounded-2xl">
              <svg className="w-7 h-7 text-gray-400 dark:text-dark-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-gray-900 dark:text-white font-medium mb-1">Nothing due</p>
            <p className="text-gray-500 dark:text-dark-400 text-xs mb-4">No upcoming deadlines.</p>
            <Link to="/schedule" className="inline-block px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-xs font-semibold rounded-lg transition-colors">
              Open Schedule Planner
            </Link>
          </div>
        )}

        {hardDeadlines.map(e => {
          const days = daysUntil(e.event_date);
          const badge = daysBadge(days);
          return (
            <div key={e.id} className="flex items-center gap-3 bg-gray-50 dark:bg-white/5 rounded-xl px-3 py-2.5 border border-gray-100 dark:border-white/5">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${badge.cls}`}>{badge.text}</span>
              <div className="flex-1 min-w-0">
                <p className="text-gray-900 dark:text-white text-sm font-medium truncate">{e.title}</p>
                <p className="text-gray-500 dark:text-dark-500 text-xs">{e.event_date}</p>
              </div>
              <span className="text-red-500 dark:text-red-400/60 text-xs font-medium flex-shrink-0">Deadline</span>
            </div>
          );
        })}

        {milestones.slice(0, 5).map(m => {
          const days = daysUntil(m.target_date);
          const badge = daysBadge(days);
          return (
            <div key={m.id} className="flex items-center gap-3 bg-gray-50 dark:bg-white/5 rounded-xl px-3 py-2.5 border border-gray-100 dark:border-white/5">
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${badge.cls}`}>{badge.text}</span>
              <div className="flex-1 min-w-0">
                <p className="text-gray-900 dark:text-white text-sm font-medium truncate">{m.title}</p>
                <p className="text-gray-500 dark:text-dark-500 text-xs">{m.projectName}</p>
              </div>
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                m.status === 'in_progress' ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400' : 'bg-gray-100 dark:bg-dark-700 text-gray-500 dark:text-dark-400'
              }`}>{m.status === 'in_progress' ? 'Active' : 'Pending'}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

