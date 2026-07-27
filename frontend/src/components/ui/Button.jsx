import Spinner from './Spinner';

const variants = {
  // Editorial: primary is solid ink, accent is the orange, secondary is a paper outline.
  primary: 'bg-dark-50 hover:bg-dark-100 text-dark-950 border border-transparent',
  accent: 'bg-primary-500 hover:bg-primary-600 text-white border border-transparent',
  secondary: 'bg-transparent hover:bg-dark-700 text-dark-50 border border-dark-600',
  danger: 'bg-red-600 hover:bg-red-700 text-white',
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
      className={`inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant] || variants.primary} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Spinner className="w-4 h-4" />}
      {children}
    </button>
  );
}
