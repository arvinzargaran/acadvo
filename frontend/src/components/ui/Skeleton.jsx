export default function Skeleton({ className = '' }) {
  return (
    <div className={`skeleton-shimmer bg-dark-700/50 rounded-lg ${className}`} />
  );
}
