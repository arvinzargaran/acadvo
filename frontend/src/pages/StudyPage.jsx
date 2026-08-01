import { useState, useEffect } from 'react';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Skeleton from '../components/ui/Skeleton';
import PageHeader from '../components/ui/PageHeader';
import Stat from '../components/ui/Stat';
import { logStudySession, getStudyStats } from '../api/study';
import toast from 'react-hot-toast';

export default function StudyPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Timer state
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const [isActive, setIsActive] = useState(false);
  const [isBreak, setIsBreak] = useState(false);
  const [customMinutes, setCustomMinutes] = useState(25);

  const loadStats = async () => {
    try {
      const res = await getStudyStats();
      setStats(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  useEffect(() => {
    let interval = null;
    if (isActive && timeLeft > 0) {
      interval = setInterval(() => setTimeLeft(prev => prev - 1), 1000);
    } else if (isActive && timeLeft === 0) {
      handleTimerEnd();
    }
    return () => clearInterval(interval);
  }, [isActive, timeLeft]);

  const handleTimerEnd = async () => {
    setIsActive(false);
    if (!isBreak) {
      // Log session
      try {
        await logStudySession({ duration_minutes: customMinutes });
        await loadStats();
        toast.success(`Logged ${customMinutes} minutes of focus!`);
      } catch (e) {
        console.error(e);
        toast.error('Failed to log session');
      }
      setIsBreak(true);
      setTimeLeft(5 * 60); // 5 min break
    } else {
      setIsBreak(false);
      setTimeLeft(customMinutes * 60);
    }
  };

  const toggleTimer = () => setIsActive(!isActive);

  const resetTimer = () => {
    setIsActive(false);
    setTimeLeft((isBreak ? 5 : customMinutes) * 60);
  };

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  if (loading) return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <Skeleton className="h-9 w-48" />
          <Skeleton className="h-4 w-80 mt-3" />
        </div>
        <div className="flex gap-4">
          <Skeleton className="h-16 w-40 rounded-2xl" />
          <Skeleton className="h-16 w-40 rounded-2xl" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Skeleton className="h-96 w-full rounded-2xl" />
        </div>
        <div className="space-y-6">
          <Skeleton className="h-40 w-full rounded-2xl" />
          <Skeleton className="h-56 w-full rounded-2xl" />
        </div>
      </div>
    </div>
  );

  const percentGoal = stats ? Math.min(100, Math.round((stats.today_minutes / stats.daily_goal_minutes) * 100)) : 0;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <PageHeader
        className="mb-8"
        eyebrow="STUDY FOCUS"
        title="Study Focus"
        subtitle="Lock in, track your time, and burn through your goals."
        actions={
          stats && (
            <div className="flex gap-3">
              <div className="card-rich shadow-editorial ring-1 ring-black/5 dark:ring-white/10 rounded-2xl px-5 py-3 flex items-center gap-3">
                <span className="icon-chip inline-flex items-center justify-center w-9 h-9 rounded-xl text-primary-600 dark:text-primary-400 flex-shrink-0">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
                  </svg>
                </span>
                <Stat label="Streak" value={stats.current_streak} unit="days" />
              </div>
              <div className="card-rich shadow-editorial ring-1 ring-black/5 dark:ring-white/10 rounded-2xl px-5 py-3 flex items-center gap-3">
                <span className="icon-chip inline-flex items-center justify-center w-9 h-9 rounded-xl text-primary-600 dark:text-primary-400 flex-shrink-0">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <Stat label="Today" value={stats.today_minutes} unit={`/ ${stats.daily_goal_minutes}m`} />
              </div>
            </div>
          )
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card className="flex flex-col items-center justify-center py-16 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-dark-700/60 z-10">
              <div className="h-full bg-primary-500 transition-all duration-1000 ease-linear" style={{ width: `${((isBreak ? 5 * 60 : customMinutes * 60) - timeLeft) / (isBreak ? 5 * 60 : customMinutes * 60) * 100}%` }} />
            </div>

            <div className="mb-8 flex gap-2">
              <button onClick={() => { setIsBreak(false); setCustomMinutes(25); setTimeLeft(25 * 60); setIsActive(false); }} className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${!isBreak && customMinutes === 25 ? 'bg-primary-500 text-white' : 'bg-dark-800 text-dark-400 hover:text-dark-50'}`}>Pomodoro (25m)</button>
              <button onClick={() => { setIsBreak(false); setCustomMinutes(50); setTimeLeft(50 * 60); setIsActive(false); }} className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${!isBreak && customMinutes === 50 ? 'bg-primary-500 text-white' : 'bg-dark-800 text-dark-400 hover:text-dark-50'}`}>Deep Work (50m)</button>
              <button onClick={() => { setIsBreak(true); setTimeLeft(5 * 60); setIsActive(false); }} className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${isBreak ? 'bg-emerald-500 text-white' : 'bg-dark-800 text-dark-400 hover:text-dark-50'}`}>Break (5m)</button>
            </div>

            <div className={`font-display text-[8rem] leading-none font-semibold tabular-nums tracking-tight mb-12 ${isBreak ? 'text-emerald-500 dark:text-emerald-400' : 'text-dark-50'}`}>
              {formatTime(timeLeft)}
            </div>

            <div className="flex gap-4">
              <Button onClick={toggleTimer} size="lg" className={`w-40 text-lg shadow-xl shadow-primary-500/20 ${isActive ? 'bg-dark-700 hover:bg-dark-600 text-dark-50' : isBreak ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-primary-600 hover:bg-primary-500 text-white'}`}>
                {isActive ? 'Pause' : 'Start'}
              </Button>
              <Button onClick={resetTimer} variant="secondary" size="lg" className="w-24 text-lg">
                Reset
              </Button>
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <h2 className="font-display text-xl text-dark-50 mb-6 flex items-center justify-between">
              <span>Daily Goal Progress</span>
              <span className="font-display tabular-nums text-primary-600 dark:text-primary-400">{percentGoal}%</span>
            </h2>
            <div className="w-full bg-dark-700 rounded-full h-4 mb-4 overflow-hidden">
              <div className="bg-primary-500 h-4 rounded-full transition-all duration-1000" style={{ width: `${percentGoal}%` }} />
            </div>
            <p className="text-dark-400 text-sm">
              {stats?.today_minutes >= stats?.daily_goal_minutes
                ? 'Daily goal reached — your streak is safely extended.'
                : `${stats?.daily_goal_minutes - stats?.today_minutes} minutes left to extend your streak to ${stats?.current_streak + 1} ${stats?.current_streak + 1 === 1 ? 'day' : 'days'}.`}
            </p>
          </Card>

          <Card>
            <h2 className="font-display text-xl text-dark-50 mb-6">Activity This Week</h2>
            <div className="flex items-end justify-between h-32 gap-2 mt-4">
              {stats?.week_activity.map((mins, i) => {
                const height = Math.max(10, Math.min(100, (mins / (stats.daily_goal_minutes || 60)) * 100));
                const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
                const dayStr = days[(new Date().getDay() - 6 + i + 7) % 7];
                const isToday = i === 6;
                return (
                  <div key={i} className="flex flex-col items-center flex-1 gap-2 group relative">
                    <div className="w-full bg-dark-700 rounded-t-sm rounded-b-lg flex items-end overflow-hidden">
                      <div
                        className={`w-full transition-all duration-500 rounded-t-sm rounded-b-lg ${isToday ? 'bg-primary-500' : (mins >= stats.daily_goal_minutes ? 'bg-primary-300 dark:bg-primary-400/70' : 'bg-dark-500')}`}
                        style={{ height: `${height}%` }}
                      ></div>
                    </div>
                    <span className={`text-xs font-medium tabular-nums ${isToday ? 'text-primary-600 dark:text-primary-400' : 'text-dark-400'}`}>{dayStr}</span>
                    <div className="absolute -top-10 bg-dark-50 text-dark-950 text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                      {mins} mins
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
