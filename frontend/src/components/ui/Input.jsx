export default function Input({ label, error, className = '', ...rest }) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-dark-300">
          {label}
        </label>
      )}
      <input
        className={`w-full bg-dark-800 border border-dark-600 text-dark-50 rounded-lg px-3 py-2 text-sm placeholder-dark-400 focus:border-primary-500 transition-colors ${
          error ? 'border-red-500' : ''
        } ${className}`}
        {...rest}
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
