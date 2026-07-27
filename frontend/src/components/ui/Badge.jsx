const colorMap = {
  green: 'bg-green-500/20 text-green-400',
  yellow: 'bg-yellow-500/20 text-yellow-400',
  red: 'bg-red-500/20 text-red-400',
  blue: 'bg-primary-500/20 text-primary-400',
  gray: 'bg-dark-600/50 text-dark-300',
};

export default function Badge({ children, color = 'gray' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        colorMap[color] || colorMap.gray
      }`}
    >
      {children}
    </span>
  );
}
