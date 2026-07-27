import Card from '../ui/Card';

function generateAlerts({ summary, courses, projects, events }) {
  const alerts = [];

  // GPA alert
  if (summary?.cumulative_gpa != null && summary.cumulative_gpa < 2.5) {
    alerts.push({
      id: 'low-gpa',
      severity: 'high',
      message: `Your GPA is ${summary.cumulative_gpa.toFixed(2)} — consider meeting with an academic advisor.`,
    });
  } else if (summary?.cumulative_gpa != null && summary.cumulative_gpa < 3.0) {
    alerts.push({
      id: 'gpa-warning',
      severity: 'medium',
      message: `Your GPA (${summary.cumulative_gpa.toFixed(2)}) is below 3.0 — focus on stronger performance this semester.`,
    });
  }

  // At-risk buckets
  const atRiskBuckets = summary?.buckets?.filter(b => b.at_risk) || [];
  if (atRiskBuckets.length > 0) {
    alerts.push({
      id: 'at-risk-buckets',
      severity: 'medium',
      message: `${atRiskBuckets.length} requirement bucket${atRiskBuckets.length > 1 ? 's are' : ' is'} at risk: ${atRiskBuckets.map(b => b.bucket_name).join(', ')}`,
    });
  }

  // No courses in progress
  const inProgress = courses?.filter(c => c.status === 'in_progress') || [];
  if (courses?.length > 0 && inProgress.length === 0) {
    alerts.push({
      id: 'no-in-progress',
      severity: 'low',
      message: 'No courses currently in progress — update your course statuses.',
    });
  }

  // Upcoming hard deadlines within 7 days
  const now = new Date();
  const urgentDeadlines = (events || []).filter(e => {
    if (!e.is_hard_deadline) return false;
    const days = Math.ceil((new Date(e.event_date) - now) / (1000 * 60 * 60 * 24));
    return days >= 0 && days <= 7;
  });
  if (urgentDeadlines.length > 0) {
    alerts.push({
      id: 'urgent-deadlines',
      severity: 'high',
      message: `${urgentDeadlines.length} deadline${urgentDeadlines.length > 1 ? 's' : ''} within 7 days!`,
    });
  }

  // No projects
  if (!projects || projects.length === 0) {
    alerts.push({
      id: 'no-projects',
      severity: 'low',
      message: 'No portfolio projects yet — start building to strengthen your applications.',
    });
  }

  // Overdue milestones
  const overdueMilestones = [];
  projects?.forEach(p => {
    p.milestones?.forEach(m => {
      if (m.target_date && m.status !== 'complete') {
        const days = Math.ceil((new Date(m.target_date) - now) / (1000 * 60 * 60 * 24));
        if (days < 0) overdueMilestones.push(m);
      }
    });
  });
  if (overdueMilestones.length > 0) {
    alerts.push({
      id: 'overdue-milestones',
      severity: 'medium',
      message: `${overdueMilestones.length} project milestone${overdueMilestones.length > 1 ? 's are' : ' is'} overdue.`,
    });
  }

  return alerts;
}

const severityConfig = {
  high: { bg: 'bg-red-500/10', border: 'border-red-500/30', dot: 'bg-red-500', text: 'text-red-300' },
  medium: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', dot: 'bg-yellow-500', text: 'text-yellow-300' },
  low: { bg: 'bg-primary-500/10', border: 'border-primary-500/30', dot: 'bg-primary-500', text: 'text-primary-300' },
};

export default function SmartAlerts({ summary, courses, projects, events }) {
  const alerts = generateAlerts({ summary, courses, projects, events });

  if (alerts.length === 0) return null;

  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-5 shadow-sm">
      <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
        <svg className="w-4 h-4 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.832c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        Smart Alerts
        <span className="text-dark-500 text-xs font-normal">({alerts.length})</span>
      </h3>
      <div className="space-y-2">
        {alerts.map(alert => {
          const cfg = severityConfig[alert.severity];
          return (
            <div key={alert.id} className={`flex items-center gap-3 px-3 py-2 rounded-xl border ${cfg.bg} ${cfg.border}`}>
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
              <p className={`text-sm ${cfg.text}`}>{alert.message}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
