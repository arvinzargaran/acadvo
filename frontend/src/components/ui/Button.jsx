import Spinner from './Spinner';

// Signage plates. Depth is a hard offset edge, not a soft shadow, and the
// press state collapses the plate onto its backing rather than scaling it.
const variants = {
  primary:
    'bg-dark-50 text-dark-950 border-2 border-dark-50 hover:bg-primary-500 hover:border-primary-500 hover:text-white',
  accent:
    'bg-primary-500 text-white border-2 border-primary-500 hover:bg-primary-600 hover:border-primary-600',
  secondary:
    'bg-transparent text-dark-50 border-2 border-dark-50 hover:bg-dark-50 hover:text-dark-950',
  ghost:
    'bg-transparent text-dark-300 border-2 border-transparent hover:bg-dark-700 hover:text-dark-50',
  danger:
    'bg-red-500 text-white border-2 border-red-500 hover:bg-red-600 hover:border-red-600',
};

export default function Button({
  variant = 'primary',
  children,
  className = '',
  disabled,
  loading,
  ...rest
}) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold transition-colors duration-150 active:translate-y-px disabled:opacity-45 disabled:cursor-not-allowed ${
        variants[variant] || variants.primary
      } ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Spinner className="w-4 h-4" />}
      {children}
    </button>
  );
}
