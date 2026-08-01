/**
 * Editorial stat / figure — a big display number with an eyebrow label.
 * Purely presentational.
 *
 * Props:
 *  - value   string | number, rendered big in Fraunces
 *  - label   string, uppercase tracked eyebrow beneath/above the figure
 *  - unit    optional string, small muted suffix after the value
 *  - sub     optional secondary muted line
 *  - className passthrough on the wrapper
 */
export default function Stat({ value, label, unit, sub, className = '' }) {
  return (
    <div className={className}>
      {label && (
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-dark-400">
          {label}
        </p>
      )}
      <p className="mt-1 flex items-baseline gap-1 font-display tabular-nums text-3xl sm:text-4xl text-dark-50">
        {value}
        {unit && <span className="text-base font-normal text-dark-400">{unit}</span>}
      </p>
      {sub && <p className="mt-0.5 text-sm text-dark-400">{sub}</p>}
    </div>
  );
}
