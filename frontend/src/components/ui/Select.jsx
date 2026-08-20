import { useState, useRef, useEffect, useId } from 'react';

export default function Select({
  label,
  error,
  className = '',
  options = [],
  placeholder = 'Select...',
  searchable = false,
  value,
  onChange,
  id,
  ...rest
}) {
  const generatedId = useId();
  const selectId = id || generatedId;
  const errorId = `${selectId}-error`;

  const normalized = options.map((o) =>
    typeof o === 'string' ? { value: o, label: o } : o
  );

  if (!searchable) {
    return (
      <div className="space-y-1">
        {/* htmlFor, not a bare <label>: without it this control has no
            accessible name, and "University" is exactly the kind of field
            nobody can guess from its options. */}
        {label && (
          <label htmlFor={selectId} className="block text-sm font-medium text-dark-300">
            {label}
          </label>
        )}
        <select
          id={selectId}
          value={value || ''}
          onChange={onChange}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? errorId : undefined}
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
        {error && (
          <p id={errorId} className="text-xs text-red-400">
            {error}
          </p>
        )}
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
      id={selectId}
      {...rest}
    />
  );
}

/**
 * Type-to-filter combobox.
 *
 * This was a text input next to a `<ul>` of `<li onClick>` rows: no roles, no
 * `aria-expanded`, nothing focusable in the list, and the only keyboard path
 * was Enter, which silently picked the first match. A keyboard or screen-reader
 * user could not see the options, let alone choose among them — and this is the
 * control that asks for the student's university and program during onboarding,
 * so failing it means never getting into the app at all.
 *
 * Rebuilt on the ARIA combobox pattern: the input owns the listbox, arrow keys
 * move an `aria-activedescendant` highlight, Enter takes the highlighted option
 * (not merely the first), and Escape closes without choosing.
 */
function SearchableSelect({
  label,
  error,
  className,
  options,
  placeholder,
  value,
  onChange,
  id,
}) {
  const [query, setQuery] = useState(value || '');
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const ref = useRef(null);
  const listRef = useRef(null);

  const listId = `${id}-listbox`;
  const errorId = `${id}-error`;

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

  // The highlight is an index into a list that shrinks as the user types, so it
  // has to be clamped on every render or Enter can select a stale row.
  const active = activeIndex >= 0 && activeIndex < filtered.length ? activeIndex : -1;
  const activeId = active >= 0 ? `${id}-option-${active}` : undefined;

  useEffect(() => {
    if (active < 0 || !listRef.current) return;
    listRef.current.children[active]?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  function select(val) {
    setQuery(val);
    setOpen(false);
    setActiveIndex(-1);
    onChange?.({ target: { value: val } });
  }

  function handleKeyDown(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        setActiveIndex(0);
        return;
      }
      const step = e.key === 'ArrowDown' ? 1 : -1;
      const next = active < 0 ? 0 : (active + step + filtered.length) % filtered.length;
      setActiveIndex(filtered.length ? next : -1);
      return;
    }
    if (e.key === 'Enter') {
      if (!open || !filtered.length) return;
      e.preventDefault();
      // The highlighted row, falling back to the single match. Previously this
      // always took filtered[0], so arrowing down and pressing Enter chose
      // something other than what was highlighted.
      select(filtered[active >= 0 ? active : 0].value);
      return;
    }
    if (e.key === 'Escape') {
      setOpen(false);
      setActiveIndex(-1);
    }
  }

  return (
    <div className="space-y-1 relative" ref={ref}>
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-gray-700 dark:text-dark-300">
          {label}
        </label>
      )}
      <input
        id={id}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? errorId : undefined}
        autoComplete="off"
        value={query}
        placeholder={placeholder}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActiveIndex(-1);
          if (!e.target.value) {
            onChange?.({ target: { value: '' } });
          }
        }}
        onKeyDown={handleKeyDown}
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
      <ul
        id={listId}
        ref={listRef}
        role="listbox"
        // Deliberately not the bare field name: an identical accessible name on
        // both the input and its popup makes the two indistinguishable to
        // anything querying by name, assistive tech included.
        aria-label={`${label || placeholder} options`}
        hidden={!open || filtered.length === 0}
        className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto bg-dark-800 border border-dark-600 rounded-lg shadow-editorial"
      >
        {filtered.map((o, i) => (
          <li
            key={o.value}
            id={`${id}-option-${i}`}
            role="option"
            aria-selected={o.value === value}
            // The input keeps focus throughout (that is the combobox pattern),
            // so mousedown rather than click: click fires after the blur that
            // the outside-click handler uses to close the list.
            onMouseDown={(e) => {
              e.preventDefault();
              select(o.value);
            }}
            onMouseEnter={() => setActiveIndex(i)}
            className={`px-3 py-2 text-sm cursor-pointer transition-colors ${
              i === active
                ? 'bg-primary-600 text-white'
                : o.value === value
                  ? 'bg-primary-600/60 text-white'
                  : 'text-dark-200 hover:bg-dark-700'
            }`}
          >
            {o.label}
          </li>
        ))}
      </ul>
      {error && (
        <p id={errorId} className="text-xs text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
