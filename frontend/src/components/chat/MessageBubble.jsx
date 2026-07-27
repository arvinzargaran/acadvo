import ReactMarkdown from 'react-markdown';
import ToolCallResult from './ToolCallResult';

export default function MessageBubble({ role, content, toolCalls }) {
  const isUser = role === 'user';

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-4`}>
      {!isUser && (
        <span className="text-xs text-dark-400 mb-1 ml-1">Acadvo</span>
      )}

      <div
        className={`max-w-[80%] px-4 py-3 ${
          isUser
            ? 'bg-primary-600 text-white rounded-2xl rounded-br-sm'
            : 'bg-dark-800 border border-dark-700 text-white rounded-2xl rounded-bl-sm'
        }`}
      >
        <div className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
      </div>

      {toolCalls && toolCalls.length > 0 && (
        <div className={`mt-2 max-w-[80%] ${isUser ? 'self-end' : 'self-start'}`}>
          <ToolCallResult toolCalls={toolCalls} />
        </div>
      )}
    </div>
  );
}
