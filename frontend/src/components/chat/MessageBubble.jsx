import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
            ? 'bg-primary-600 text-white rounded-2xl rounded-br-sm shadow-sm'
            : 'bg-dark-800 border border-dark-700 text-dark-50 rounded-2xl rounded-bl-sm'
        }`}
      >
        {/* GFM, not plain CommonMark. The advisor answers comparisons as
            tables — "which course and why" comes back as reason/benefit rows —
            and without this plugin every one of them renders as a wall of
            literal pipes and dashes. Tables get their own overflow wrapper
            because a three-column table does not fit an 80%-width bubble. */}
        <div
          className={`prose prose-sm max-w-none prose-table:block prose-table:overflow-x-auto ${
            isUser ? 'prose-invert' : 'dark:prose-invert'
          }`}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
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
