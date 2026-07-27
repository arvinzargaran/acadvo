import Card from '../ui/Card';
import ProgressRing from '../ui/ProgressRing';

export default function PortfolioScore({ projects }) {
  if (!projects) return null;

  const total = projects.length;
  const ready = projects.filter(p => p.status === 'deployed' || p.status === 'interview_ready').length;
  const inProgress = projects.filter(p => p.status === 'in_progress').length;

  const score = total === 0 ? 0 : Math.round((ready / Math.max(total, 3)) * 100);
  const ringColor = score >= 66 ? '#4ade80' : score >= 33 ? '#facc15' : '#f87171';

  return (
    <Card gradient>
      <p className="text-dark-400 text-sm mb-3">Portfolio Readiness</p>
      <div className="flex items-center gap-4">
        <ProgressRing value={score} size={80} strokeWidth={6} color={ringColor} label="" />
        <div className="text-sm text-dark-300">
          <p>{ready} deployed / ready</p>
          <p>{inProgress} in progress</p>
          <p>{total} total projects</p>
        </div>
      </div>
    </Card>
  );
}
