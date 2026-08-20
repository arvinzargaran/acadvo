export default function ProgressBar({ value = 0, label, className = '' }) {
  return (
    <div className={className}>
      {label && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium text-dark-300">{label}</span>
          <span className="text-sm text-dark-400">{Math.round(value)}%</span>
        </div>
      )}
      {/* A progress bar is a length of track, not a pill: square ends, one
          flat colour, so it reads as the same object as the route lines
          elsewhere in the product. */}
      <div className="w-full h-2 bg-[var(--wf-sunk)] border border-[var(--wf-rule)] overflow-hidden">
        <div
          className="h-full bg-[var(--wf-live)] transition-[width] duration-300"
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
    </div>
  );
}
