import { useState, useEffect, useRef } from 'react';
import useConversation from '../../hooks/useConversation';
import MessageBubble from '../chat/MessageBubble';
import ChatInput from '../chat/ChatInput';

const CAREER_QUICK_ACTIONS = [
  'Build my career plan based on my profile and goals',
  'What companies should I target for co-op?',
  'Create a timeline to land a SWE internship',
  'What skills should I focus on this semester?',
  'Review my application pipeline and suggest next steps',
  'Help me prepare for technical interviews',
];

export default function CareerAIChat({ targets, events, onClose, onDataChanged }) {
  const {
    messages,
    loading,
    sending,
    initConversation,
    sendMessage,
  } = useConversation();
  const messagesEndRef = useRef(null);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    initConversation(false);
    // Mount-only: starting a second conversation because the hook handed back a
    // new function identity is exactly the bug the dependency would cause.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (text) => {
    setStarted(true);
    await sendMessage(text);
    // Refresh career data after AI responds (it may have created targets/events)
    if (onDataChanged) onDataChanged();
  };

  const handleQuickAction = (text) => {
    handleSend(text);
  };

  return (
    <div className="fixed inset-0 z-50 bg-dark-900 flex">
      {/* Left: AI Chat */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="h-14 border-b border-dark-700 flex items-center justify-between px-6 bg-primary-500/5 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="text-dark-400 hover:text-dark-50 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </button>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-400" />
              <h2 className="text-dark-50 font-semibold text-sm">Career AI Advisor</h2>
            </div>
          </div>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {!started && !loading && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full max-w-lg mx-auto text-center">
              <div className="w-16 h-16 rounded-full bg-primary-500 flex items-center justify-center mb-6">
                <svg className="w-8 h-8 text-dark-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-dark-50 mb-2">Career AI Advisor</h3>
              <p className="text-dark-400 text-sm mb-8">
                I'll help you build a career plan, find target companies, create timelines, and prepare for applications — all based on your profile, degree progress, and goals.
              </p>
              <div className="grid grid-cols-2 gap-3 w-full">
                {CAREER_QUICK_ACTIONS.map((action) => (
                  <button
                    key={action}
                    onClick={() => handleQuickAction(action)}
                    className="bg-dark-800 hover:bg-dark-700 border border-dark-600 hover:border-dark-500 text-dark-300 hover:text-dark-50 text-sm px-4 py-3 rounded-xl transition-all text-left"
                  >
                    {action}
                  </button>
                ))}
              </div>
            </div>
          )}

          {loading && (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
            </div>
          )}

          {(started || messages.length > 0) && !loading && (
            <div className="max-w-2xl mx-auto space-y-1">
              {messages.map((msg, i) => (
                <MessageBubble
                  key={i}
                  role={msg.role}
                  content={msg.content}
                  toolCalls={msg.tool_calls}
                />
              ))}
              {sending && (
                <div className="flex items-start mb-4">
                  <div className="bg-dark-800 border border-dark-700 rounded-2xl rounded-bl-sm px-4 py-3">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-dark-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-dark-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-dark-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="max-w-2xl mx-auto w-full">
          <ChatInput
            onSend={handleSend}
            disabled={sending || loading}
            placeholder="Ask about career planning, co-op targets, interview prep..."
          />
        </div>
      </div>

      {/* Right: Context Panel */}
      <div className="w-80 border-l border-dark-700 bg-dark-800 flex flex-col overflow-hidden hidden lg:flex">
        <div className="px-4 py-3 border-b border-dark-700 flex-shrink-0">
          <h3 className="text-dark-50 font-semibold text-sm">Your Career Data</h3>
          <p className="text-dark-500 text-xs mt-0.5">Live context for the AI</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Targets */}
          <div>
            <h4 className="text-dark-400 text-xs font-medium uppercase tracking-wide mb-2">
              Targets ({targets.length})
            </h4>
            {targets.length === 0 ? (
              <p className="text-dark-500 text-xs">None yet — ask the AI to suggest some!</p>
            ) : (
              <div className="space-y-1.5">
                {targets.map(t => (
                  <div key={t.id} className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-2">
                    <p className="text-dark-50 text-xs font-medium">{t.company_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      {t.role_type && <span className="text-dark-400 text-[10px]">{t.role_type}</span>}
                      <StatusBadge status={t.status} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Timeline */}
          <div>
            <h4 className="text-dark-400 text-xs font-medium uppercase tracking-wide mb-2">
              Timeline ({events.length})
            </h4>
            {events.length === 0 ? (
              <p className="text-dark-500 text-xs">No events yet</p>
            ) : (
              <div className="space-y-1.5">
                {events.slice(0, 8).map(e => (
                  <div key={e.id} className="flex items-center gap-2 px-3 py-1.5 bg-dark-800 border border-dark-700 rounded-lg">
                    <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${e.is_hard_deadline ? 'bg-red-500' : 'bg-primary-500'}`} />
                    <div className="min-w-0">
                      <p className="text-dark-50 text-[11px] truncate">{e.title}</p>
                      <p className="text-dark-500 text-[10px]">{e.event_date}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Pipeline summary */}
          <div>
            <h4 className="text-dark-400 text-xs font-medium uppercase tracking-wide mb-2">Pipeline</h4>
            <div className="grid grid-cols-2 gap-1.5">
              {['researching', 'applied', 'interviewing', 'offer'].map(status => {
                const count = targets.filter(t => t.status === status).length;
                return (
                  <div key={status} className="bg-dark-800 border border-dark-700 rounded-lg px-2 py-1.5 text-center">
                    <p className="text-dark-50 text-sm font-bold">{count}</p>
                    <p className="text-dark-500 text-[10px] capitalize">{status}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const colors = {
    researching: 'bg-dark-600 text-dark-300',
    applied: 'bg-primary-500/20 text-primary-400',
    interviewing: 'bg-yellow-500/20 text-yellow-400',
    offer: 'bg-green-500/20 text-green-400',
    rejected: 'bg-red-500/20 text-red-400',
  };
  return (
    <span className={`text-[9px] px-1.5 py-0.5 rounded ${colors[status] || colors.researching}`}>
      {status}
    </span>
  );
}
