import { useEffect, useRef, useId } from 'react';

export default function Modal({ isOpen, onClose, title, children }) {
  const cardRef = useRef(null);
  const titleId = useId();

  // Close on Escape and trap focus within the dialog while it's open.
  useEffect(() => {
    if (!isOpen) return;

    const previouslyFocused = document.activeElement;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;

      const focusable = cardRef.current?.querySelectorAll(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
      );
      if (!focusable || focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown, true);

    // Move focus into the dialog on open.
    const firstField = cardRef.current?.querySelector(
      'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
    );
    firstField?.focus();

    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
      // Restore focus to whatever triggered the modal.
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Card */}
      <div
        ref={cardRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative bg-dark-800 border border-dark-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 id={titleId} className="text-lg font-semibold text-white">{title}</h3>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="text-dark-400 hover:text-white transition-colors"
          >
            &#x2715;
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
