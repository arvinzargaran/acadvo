import { useState, useRef, useEffect } from 'react';

export default function ChatInput({ onSend, disabled = false, placeholder = 'Type a message...' }) {
  const [value, setValue] = useState('');
  const textareaRef = useRef(null);

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 6 * 24) + 'px';
  }, [value]);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isEmpty = value.trim().length === 0;

  return (
    <div className="flex items-end gap-3 p-4 border-t border-dark-700 bg-dark-900">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none bg-dark-800 border border-dark-600 text-white rounded-xl px-4 py-3
                   placeholder-dark-400 focus:outline-none focus:ring-2 focus:ring-primary-600 focus:border-transparent
                   disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <button
        onClick={handleSend}
        disabled={isEmpty || disabled}
        className="flex-shrink-0 bg-primary-600 hover:bg-primary-700 text-white rounded-xl px-4 py-3
                   font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-5 h-5"
        >
          <path d="M3.105 2.288a.75.75 0 0 0-.826.95l1.414 4.926A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.086l-1.414 4.926a.75.75 0 0 0 .826.95l14.095-5.638a.75.75 0 0 0 0-1.398L3.105 2.288Z" />
        </svg>
      </button>
    </div>
  );
}
