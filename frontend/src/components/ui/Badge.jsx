const colorMap = {
  green: 'bg-green-500/20 text-green-400',
  yellow: 'bg-yellow-500/20 text-yellow-400',
  red: 'bg-red-500/20 text-red-400',
  blue: 'bg-primary-500/20 text-primary-400',
  gray: 'bg-dark-600/50 text-dark-300',
};

// Solid dot color per badge color, for the optional leading `dot`.
const dotMap = {
  green: 'bg-green-500',
  yellow: 'bg-yellow-500',
  red: 'bg-red-500',
  blue: 'bg-primary-500',
  gray: 'bg-dark-400',
};

export default function Badge({ children, color = 'gray', variant, dot = false }) {
  const tone = colorMap[color] || colorMap.gray;
  const base =
    variant === 'label'
      ? 'wf-signage text-[0.62rem] px-2 py-0.5'
      : 'text-xs font-medium px-2.5 py-0.5';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border border-dark-600 ${base} ${tone}`}
    >
      {dot && (
        <span className={`h-1.5 w-1.5 rounded-full ${dotMap[color] || dotMap.gray}`} />
      )}
      {children}
    </span>
  );
}
