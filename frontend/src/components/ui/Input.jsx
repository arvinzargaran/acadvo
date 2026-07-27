export default function Input({ label, error, className = '', ...rest }) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="block text-sm font-medium text-gray-700 dark:text-dark-300">
          {label}
        </label>
      )}
      <input
        className={`w-full bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm placeholder-gray-400 dark:placeholder-dark-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors ${
          error ? 'border-red-500' : ''
        } ${className}`}
        {...rest}
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
