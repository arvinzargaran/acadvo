/**
 * A flat plate. Signage has no ambient shadow, so a card reads by its rule and
 * a hard offset edge; `hover` deepens that offset and lifts the plate toward
 * the corner it is offset from, which is the only movement in the system.
 *
 * `gradient` keeps its name for the ~9 call sites that use it, but is now a
 * solid line-coloured cap rail across the top of the card.
 */
export default function Card({ children, className = '', gradient = false, hover = false }) {
  return (
    <div
      className={`card-rich shadow-editorial p-6 relative overflow-hidden ${
        hover
          ? 'transition-[box-shadow,transform] duration-200 ease-out hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[5px_5px_0_0_var(--wf-rule)]'
          : ''
      } ${className}`}
    >
      {gradient && (
        <div
          aria-hidden="true"
          className="absolute top-0 left-0 right-0 h-[3px] z-10"
          style={{ background: 'var(--wf-live)' }}
        />
      )}
      {children}
    </div>
  );
}
