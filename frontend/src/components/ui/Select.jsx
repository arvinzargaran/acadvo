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
          <label className="block text-sm font-medium text-dark-300">
            {label}
          </label>
        )}
        <select
          value={value || ''}
          onChange={onChange}
          className={`w-full bg-dark-800 border border-dark-600 text-dark-50 rounded-lg px-3 py-2 text-sm focus:border-primary-500 transition-colors ${
            error ? 'border-red-500' : ''
          } ${!value ? 'text-dark-400' : ''} ${className}`}
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
        className={`w-full bg-dark-800 border ${
          value === query ? 'border-green-500/50' : 'border-dark-600 focus:border-primary-500'
        } text-dark-50 rounded-lg px-3 py-2 text-sm placeholder-dark-400 transition-colors ${
          error ? '!border-red-500' : ''
        } ${className}`}
      />
      {open && query && value !== query && (
        <span className="absolute right-3 top-2.5 text-[10px] text-primary-600 dark:text-primary-400 font-medium px-1.5 py-0.5 rounded bg-primary-500/10">
          Select an option below ↓
        </span>
      )}
      {open && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto bg-dark-800 border border-dark-600 rounded-lg shadow-editorial">
          {filtered.map((o) => (
            <li
              key={o.value}
              onClick={() => select(o.value)}
              className={`px-3 py-2 text-sm cursor-pointer transition-colors ${
                o.value === value
                  ? 'bg-primary-600 text-white'
                  : 'text-dark-200 hover:bg-dark-700'
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
