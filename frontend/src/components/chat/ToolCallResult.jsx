import { useState } from 'react';

function ToolCallItem({ toolCall }) {
  const [expanded, setExpanded] = useState(false);
  const { tool, input, result } = toolCall;

  const isError = result?.error || result?.status === 'error';
  const accentColor = isError ? 'red' : 'green';

  return (
    <div className="rounded-lg border border-dark-700 overflow-hidden mb-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-dark-700/30 transition-colors"
      >
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
            ${isError ? 'bg-red-900/40 text-red-400' : 'bg-green-900/40 text-green-400'}`}
        >
          {tool}
        </span>

        {result?.message && (
          <span className="text-sm text-dark-300 truncate flex-1">
            {result.message}
          </span>
        )}

        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`w-4 h-4 text-dark-400 flex-shrink-0 transition-transform ${
            expanded ? 'rotate-180' : ''
          }`}
        >
          <path
            fillRule="evenodd"
            d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {!expanded && result?.message && (
        <div className="px-3 pb-2">
          <div className="bg-dark-700/50 rounded px-3 py-2 text-sm text-dark-300">
            {result.message}
          </div>
        </div>
      )}

      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          <div>
            <span className="text-xs text-dark-400 font-medium uppercase">Input</span>
            <pre className="mt-1 bg-dark-700/50 rounded px-3 py-2 text-xs text-dark-300 overflow-x-auto">
              {JSON.stringify(input, null, 2)}
            </pre>
          </div>
          <div>
            <span className="text-xs text-dark-400 font-medium uppercase">Result</span>
            <pre
              className={`mt-1 rounded px-3 py-2 text-xs overflow-x-auto ${
                isError
                  ? 'bg-red-900/20 text-red-300'
                  : 'bg-green-900/20 text-green-300'
              }`}
            >
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ToolCallResult({ toolCalls }) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="space-y-1">
      {toolCalls.map((tc, i) => (
        <ToolCallItem key={i} toolCall={tc} />
      ))}
    </div>
  );
}
