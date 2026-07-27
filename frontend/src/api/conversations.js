import client from './client';

export function createConversation(data) {
  return client.post('/conversations', data);
}

export function listConversations() {
  return client.get('/conversations');
}

export function getConversation(id) {
  return client.get(`/conversations/${id}`);
}

export function sendMessage(conversationId, content) {
  return client.post(`/conversations/${conversationId}/messages`, { content });
}

export function deleteConversation(id) {
  return client.delete(`/conversations/${id}`);
}
