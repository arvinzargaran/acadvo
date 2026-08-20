import { useId } from 'react';

/**
 * A labelled text field.
 *
 * The label used to be a bare `<label>` sitting *beside* the input with no
 * `htmlFor` — visually a label, and nothing at all to a screen reader, which
 * announced every field in the app as an unnamed edit box. Several of these
 * fields ask for a password or an email address, so "edit box, blank" is the
 * whole prompt a non-sighted user got. A placeholder does not fix that: it is
 * not an accessible name, and it disappears the moment anyone types.
 */
export default function Input({ label, error, className = '', id, ...rest }) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const errorId = `${inputId}-error`;

  return (
    <div className="space-y-1">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-dark-300">
          {label}
        </label>
      )}
      <input
        id={inputId}
        // Announce the invalid state, and point at the message that says why —
        // the red border alone carries no information without sight.
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`w-full bg-dark-800 border border-dark-600 text-dark-50 rounded-lg px-3 py-2 text-sm placeholder-dark-400 focus:border-primary-500 transition-colors ${
          error ? 'border-red-500' : ''
        } ${className}`}
        {...rest}
      />
      {error && (
        <p id={errorId} className="text-xs text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
