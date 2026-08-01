import Card from '../ui/Card';
import ProgressRing from '../ui/ProgressRing';

export default function CreditProgress({ summary, bento = false }) {
  if (!summary) return bento ? <div><h3 className="text-white font-semibold mb-2">Credits</h3><p className="text-dark-400 text-sm">No degree data yet.</p></div> : null;

  const content = (
    <>
      <h3 className="text-white font-semibold mb-3">Degree Progress</h3>
      <div className="flex items-center gap-4 mb-4">
        <ProgressRing
          value={summary.overall_percentage}
          size={80}
          strokeWidth={6}
          label=""
        />
        <div className="text-sm text-dark-300 min-w-0">
          <p className="font-display tabular-nums text-white text-2xl whitespace-nowrap">{summary.total_credits_completed} / {summary.total_credits_required}</p>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-dark-400 mt-0.5">credits completed</p>
        </div>
      </div>
      <div className="space-y-3">
        {summary.buckets?.slice(0, bento ? 3 : undefined).map((bucket, i) => (
          <div key={i}>
            <div className="flex justify-between text-sm mb-1 gap-2">
              <span className={`truncate min-w-0 ${bucket.at_risk ? 'text-red-400' : 'text-dark-300'}`}>
                {bucket.bucket_name}
                {bucket.at_risk && ' ⚠'}
              </span>
              <span className="text-dark-400 flex-shrink-0">
                {bucket.credits_completed} / {bucket.credits_required}
              </span>
            </div>
            <div className="h-1.5 bg-dark-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${bucket.at_risk ? 'bg-red-500' : 'bg-primary-500'}`}
                style={{ width: `${Math.min(bucket.percentage, 100)}%` }}
              />
            </div>
          </div>
        ))}
        {bento && summary.buckets?.length > 3 && (
          <p className="text-dark-500 text-xs">+{summary.buckets.length - 3} more buckets</p>
        )}
      </div>
    </>
  );

  if (bento) return <div>{content}</div>;
  return <Card gradient>{content}</Card>;
}
