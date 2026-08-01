import { useState, useEffect, useRef } from 'react';
import useConversation from '../../hooks/useConversation';
import { listConversations, deleteConversation } from '../../api/conversations';
import MessageBubble from './MessageBubble';
import ChatInput from './ChatInput';

const QUICK_ACTIONS = [
  'Plan my next semester',
  'Suggest a project idea',
  'Review my progress',
];

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const {
    conversationId,
    messages,
    loading,
    sending,
    sendError,
    setSendError,
    initConversation,
    loadConversation,
    sendMessage,
  } = useConversation();
  const [conversations, setConversations] = useState([]);
  const [showConvList, setShowConvList] = useState(false);
  const messagesEndRef = useRef(null);
  // Live mirror of conversationId so the open-chat poll reads the current value
  // rather than the (possibly null) value captured when the event fired.
  const conversationIdRef = useRef(conversationId);
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  useEffect(() => {
    if (isOpen && !conversationId) {
      loadExistingOrCreate();
    }
  }, [isOpen]);

  // Listen for external open requests (e.g. from Career page)
  useEffect(() => {
    function handleOpenChat(e) {
      setIsOpen(true);
      const msg = e.detail?.message;
      if (msg) {
        // Wait for the conversation to be ready, then send. Reads the ref (live
        // value) and gives up after ~15s so it can't poll forever.
        let attempts = 0;
        const trySend = () => {
          if (conversationIdRef.current) {
            sendMessage(msg);
          } else if (attempts++ < 30) {
            setTimeout(trySend, 500);
          }
        };
        setTimeout(trySend, 300);
      }
    }
    window.addEventListener('open-chat-widget', handleOpenChat);
    return () => window.removeEventListener('open-chat-widget', handleOpenChat);
  }, [sendMessage]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function loadExistingOrCreate() {
    try {
      const { data } = await listConversations();
      const nonOnboarding = data.filter((c) => !c.is_onboarding);
      setConversations(nonOnboarding);
      if (nonOnboarding.length > 0) {
        await loadConversation(nonOnboarding[0].id);
      } else {
        await initConversation(false);
      }
    } catch {
      await initConversation(false);
    }
  }

  async function handleNewChat() {
    const id = await initConversation(false);
    setShowConvList(false);
    const { data } = await listConversations();
    setConversations(data.filter((c) => !c.is_onboarding));
  }

  async function handleSelectConversation(id) {
    await loadConversation(id);
    setShowConvList(false);
  }

  async function handleDeleteConversation(e, id) {
    e.stopPropagation();
    await deleteConversation(id);
    const { data } = await listConversations();
    const filtered = data.filter((c) => !c.is_onboarding);
    setConversations(filtered);
    if (id === conversationId) {
      if (filtered.length > 0) {
        await loadConversation(filtered[0].id);
      } else {
        await initConversation(false);
      }
    }
  }

  function handleQuickAction(text) {
    sendMessage(text);
  }

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-[60] group"
        data-tour="chat-widget"
      >
        <div className="btn-accent rounded-full w-14 h-14 flex items-center justify-center transition-transform group-hover:scale-105 group-active:scale-95">
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-[60] flex flex-col items-end gap-3">
      {/* Chat Panel */}
      <div className="w-[calc(100vw-3rem)] max-w-[400px] h-[520px] max-h-[calc(100vh-7rem)] bg-dark-900/95 backdrop-blur-xl border border-dark-700 rounded-2xl shadow-editorial flex flex-col overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="px-4 py-3 border-b border-dark-700 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="icon-chip flex h-8 w-8 items-center justify-center rounded-lg text-primary-600 dark:text-primary-400">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
            </span>
            <button
              onClick={() => setShowConvList(!showConvList)}
              className="font-display text-base text-dark-50 hover:text-primary-600 dark:hover:text-primary-400 transition-colors leading-none"
            >
              Acadvo AI
            </button>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleNewChat}
              className="p-1.5 text-dark-400 hover:text-dark-50 transition-colors rounded-lg hover:bg-dark-700"
              title="New chat"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 text-dark-400 hover:text-dark-50 transition-colors rounded-lg hover:bg-dark-700"
              title="Close"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Conversation list dropdown */}
        {showConvList && (
          <div className="border-b border-dark-700 max-h-40 overflow-y-auto bg-dark-800">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`flex items-center group transition-colors ${
                  conv.id === conversationId ? 'bg-primary-600/20' : 'hover:bg-dark-700'
                }`}
              >
                <button
                  onClick={() => handleSelectConversation(conv.id)}
                  className={`flex-1 text-left px-4 py-2 text-sm truncate ${
                    conv.id === conversationId ? 'text-dark-50' : 'text-dark-300'
                  }`}
                >
                  {conv.title || 'New conversation'}
                </button>
                <button
                  onClick={(e) => handleDeleteConversation(e, conv.id)}
                  className="px-2 py-2 text-dark-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                  title="Delete"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Quick actions */}
        {messages.length === 0 && !loading && (
          <div className="px-4 py-3 flex gap-2 flex-wrap border-b border-dark-700">
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action}
                onClick={() => handleQuickAction(action)}
                className="bg-dark-800 hover:bg-dark-700 text-dark-300 hover:text-dark-50 text-xs px-3 py-1.5 rounded-full transition-colors border border-dark-600"
              >
                {action}
              </button>
            ))}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-1">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-dark-400 text-sm">Loading...</div>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-dark-500 text-sm">Ask me anything about your academic plan</p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <MessageBubble
                key={i}
                role={msg.role}
                content={msg.content}
                toolCalls={msg.tool_calls}
              />
            ))
          )}
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
          {sendError && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 text-red-400 text-xs px-3 py-2 rounded-lg">
              <span className="flex-1">{sendError}</span>
              <button onClick={() => setSendError('')} className="hover:text-red-300 shrink-0">✕</button>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <ChatInput
          onSend={sendMessage}
          disabled={sending || loading}
          placeholder="Ask Acadvo..."
        />
      </div>

      {/* Minimize button */}
      <button
        onClick={() => setIsOpen(false)}
        className="btn-accent rounded-full w-10 h-10 flex items-center justify-center transition-transform hover:scale-105 active:scale-95"
      >
        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
    </div>
  );
}
