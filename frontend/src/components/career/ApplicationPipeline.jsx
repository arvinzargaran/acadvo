import Badge from '../ui/Badge';

const columns = [
  { key: 'researching', label: 'Researching', color: 'border-dark-500', badge: 'gray' },
  { key: 'applied', label: 'Applied', color: 'border-primary-500/50', badge: 'blue' },
  { key: 'interviewing', label: 'Interviewing', color: 'border-yellow-500/50', badge: 'yellow' },
  { key: 'offer', label: 'Offer', color: 'border-green-500/50', badge: 'green' },
  { key: 'rejected', label: 'Rejected', color: 'border-red-500/50', badge: 'red' },
];

export default function ApplicationPipeline({ targets, onEdit, onStatusChange }) {
  const grouped = {};
  for (const col of columns) grouped[col.key] = [];
  for (const t of targets) {
    if (grouped[t.status]) grouped[t.status].push(t);
    else grouped.researching.push(t);
  }

  return (
    <div className="flex md:grid md:grid-cols-3 lg:grid-cols-5 gap-3 overflow-x-auto md:overflow-visible snap-x snap-mandatory md:snap-none scrollbar-hide -mx-1 px-1 pb-1 md:mx-0 md:px-0 md:pb-0">
      {columns.map(col => (
        <div key={col.key} className={`bg-dark-800 ring-1 ring-black/5 dark:ring-white/10 rounded-xl border-t-2 ${col.color} min-h-[200px] w-[80%] sm:w-[46%] shrink-0 snap-start md:w-auto md:shrink`}>
          <div className="px-3 py-2.5 flex items-center justify-between">
            <Badge color={col.badge} variant="label" dot>{col.label}</Badge>
            <span className="font-display tabular-nums text-sm text-dark-400">{grouped[col.key].length}</span>
          </div>
          <div className="px-2 pb-2 space-y-2">
            {/* The whole card cannot be one button: it contains the quick
                status-advance buttons below, and nesting interactive controls is
                invalid HTML and unusable with a keyboard. The card's own action
                lives on its title instead — the standard shape for a card with
                both a primary action and secondary ones. */}
            {grouped[col.key].map(target => (
              <div
                key={target.id}
                className="bg-dark-700/70 hover:bg-dark-700 border border-dark-600 rounded-lg p-3 transition-colors"
              >
                <button
                  type="button"
                  onClick={() => onEdit(target)}
                  className="text-dark-50 text-sm font-medium text-left hover:underline"
                >
                  {target.company_name}
                </button>
                {target.role_type && (
                  <p className="text-dark-400 text-xs mt-0.5">{target.role_type}</p>
                )}
                {target.target_term && (
                  <span className="inline-block mt-1.5">
                    <Badge color="gray" variant="label">{target.target_term}</Badge>
                  </span>
                )}
                {/* Quick status advance buttons */}
                {col.key !== 'offer' && col.key !== 'rejected' && (
                  <div className="flex gap-1 mt-2">
                    {col.key === 'researching' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onStatusChange(target.id, 'applied'); }}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-primary-500/20 text-primary-300 hover:bg-primary-500/30 transition-colors"
                      >
                        Applied
                      </button>
                    )}
                    {col.key === 'applied' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); onStatusChange(target.id, 'interviewing'); }}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-300 hover:bg-yellow-500/30 transition-colors"
                      >
                        Interviewing
                      </button>
                    )}
                    {col.key === 'interviewing' && (
                      <>
                        <button
                          onClick={(e) => { e.stopPropagation(); onStatusChange(target.id, 'offer'); }}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-300 hover:bg-green-500/30 transition-colors"
                        >
                          Offer
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); onStatusChange(target.id, 'rejected'); }}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-colors"
                        >
                          Rejected
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
