/**
 * Avatar — initials monogram on a warm amber tint. Purely presentational.
 *
 * Props:
 *  - name   full name (used to derive up to two initials)
 *  - size   'sm' | 'md' | 'lg'  (default 'md')
 *  - className passthrough
 */
const sizeMap = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-9 w-9 text-sm',
  lg: 'h-11 w-11 text-base',
};

function initials(name = '') {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export default function Avatar({ name, size = 'md', className = '' }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold tracking-tight text-primary-700 dark:text-primary-300 select-none
        bg-gradient-to-br from-primary-500/25 to-primary-500/5 ring-1 ring-inset ring-primary-500/25
        ${sizeMap[size] || sizeMap.md} ${className}`}
    >
      {initials(name)}
    </span>
  );
}
