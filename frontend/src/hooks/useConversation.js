import { useState, useCallback } from 'react';
import {
  createConversation,
  getConversation,
  sendMessage as apiSendMessage,
} from '../api/conversations';

export default function useConversation() {
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState('');

  const initConversation = useCallback(async (isOnboarding = false) => {
    setLoading(true);
    try {
      const { data } = await createConversation({
        is_onboarding: isOnboarding,
      });
      const id = data.id;
      setConversationId(id);
      setMessages(data.messages || []);
      return id;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadConversation = useCallback(async (id) => {
    setLoading(true);
    try {
      const { data } = await getConversation(id);
      setConversationId(id);
      setMessages(data.messages || []);
    } finally {
      setLoading(false);
    }
  }, []);

  const sendMessage = useCallback(
    async (content) => {
      if (!conversationId) return null;
      setSending(true);
      setSendError('');

      // Optimistic user message
      const userMsg = { role: 'user', content, tool_calls: null };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const { data } = await apiSendMessage(conversationId, content);
        const assistantMsg = {
          role: 'assistant',
          content: data.content || data.message || '',
          tool_calls: data.tool_calls || null,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        return data;
      } catch (err) {
        setMessages((prev) => prev.slice(0, -1));
        const status = err.response?.status;
        const detail = err.response?.data?.detail;
        if (status === 429) {
          setSendError(detail || 'Rate limit reached. Please wait a moment.');
        } else if (status === 503) {
          setSendError(detail || 'AI service is temporarily unavailable.');
        } else {
          setSendError(detail || 'Failed to send message. Please try again.');
        }
        throw err;
      } finally {
        setSending(false);
      }
    },
    [conversationId]
  );

  return {
    conversationId,
    messages,
    loading,
    sending,
    sendError,
    setSendError,
    initConversation,
    loadConversation,
    sendMessage,
  };
}
