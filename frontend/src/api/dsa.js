import client from './client';

export function listProblems() {
  return client.get('/dsa/problems');
}

export function createProblem(data) {
  return client.post('/dsa/problems', data);
}

export function updateProblem(id, data) {
  return client.put(`/dsa/problems/${id}`, data);
}

export function deleteProblem(id) {
  return client.delete(`/dsa/problems/${id}`);
}

export function getStats() {
  return client.get('/dsa/stats');
}

export function getSettings() {
  return client.get('/dsa/settings');
}

export function updateSettings(data) {
  return client.put('/dsa/settings', data);
}
