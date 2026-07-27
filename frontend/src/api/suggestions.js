import client from './client';

export function listSuggestions() {
  return client.get('/suggestions');
}

export function updateSuggestion(id, data) {
  return client.put(`/suggestions/${id}`, data);
}
