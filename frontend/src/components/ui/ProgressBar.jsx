export default function ProgressBar({ value = 0, label, className = '' }) {
  return (
    <div className={className}>
      {label && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium text-dark-300">{label}</span>
          <span className="text-sm text-dark-400">{Math.round(value)}%</span>
        </div>
      )}
      <div className="w-full h-2 bg-dark-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-primary-400 to-primary-600 rounded-full transition-all duration-300"
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
    </div>
  );
}
