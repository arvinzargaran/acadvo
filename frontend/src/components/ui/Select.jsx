import { useState, useRef, useEffect } from 'react';

export default function Select({
  label,
  error,
  className = '',
  options = [],
  placeholder = 'Select...',
  searchable = false,
  value,
  onChange,
  ...rest
}) {
  const normalized = options.map((o) =>
    typeof o === 'string' ? { value: o, label: o } : o
  );

  if (!searchable) {
    return (
      <div className="space-y-1">
        {label && (
          <label className="block text-sm font-medium text-gray-700 dark:text-dark-300">
            {label}
          </label>
        )}
        <select
          value={value || ''}
          onChange={onChange}
          className={`w-full bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors ${
            error ? 'border-red-500' : ''
          } ${!value ? 'text-gray-400 dark:text-dark-400' : ''} ${className}`}
          {...rest}
        >
          <option value="" disabled>
            {placeholder}
          </option>
          {normalized.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {error && <p className="text-xs text-red-400">{error}</p>}
      </div>
    );
  }

  return (
    <SearchableSelect
      label={label}
      error={error}
      className={className}
      options={normalized}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      {...rest}
    />
  );
}

function SearchableSelect({
  label,
  error,
  className,
  options,
  placeholder,
  value,
  onChange,
}) {
  const [query, setQuery] = useState(value || '');
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    setQuery(value || '');
  }, [value]);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const filtered = options.filter((o) =>
    o.label.toLowerCase().includes(query.toLowerCase())
  );

  function select(val) {
    setQuery(val);
    setOpen(false);
    onChange?.({ target: { value: val } });
  }

  return (
    <div className="space-y-1 relative" ref={ref}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 dark:text-dark-300">
          {label}
        </label>
      )}
      <input
        type="text"
        value={query}
        placeholder={placeholder}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          if (!e.target.value) {
            onChange?.({ target: { value: '' } });
          }
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && open && filtered.length > 0) {
            e.preventDefault();
            select(filtered[0].value);
          }
        }}
        onFocus={() => setOpen(true)}
        className={`w-full bg-white dark:bg-dark-800 border ${
          value === query ? 'border-green-500/50 focus:ring-green-500' : 'border-gray-200 dark:border-dark-600 focus:ring-primary-500'
        } text-gray-900 dark:text-white rounded-lg px-3 py-2 text-sm placeholder-gray-400 dark:placeholder-dark-400 focus:outline-none focus:ring-2 focus:border-transparent transition-colors ${
          error ? '!border-red-500 focus:ring-red-500' : ''
        } ${className}`}
      />
      {open && query && value !== query && (
        <span className="absolute right-3 top-2.5 text-[10px] text-primary-600 dark:text-primary-400 font-medium px-1.5 py-0.5 rounded bg-primary-500/10">
          Select an option below ↓
        </span>
      )}
      {open && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-600 rounded-lg shadow-xl">
          {filtered.map((o) => (
            <li
              key={o.value}
              onClick={() => select(o.value)}
              className={`px-3 py-2 text-sm cursor-pointer transition-colors ${
                o.value === value
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-700 dark:text-dark-200 hover:bg-gray-100 dark:hover:bg-dark-700'
              }`}
            >
              {o.label}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
