import client from './client';

export function listCareerTargets() {
  return client.get('/career/targets');
}

export function createCareerTarget(data) {
  return client.post('/career/targets', data);
}

export function updateCareerTarget(id, data) {
  return client.put(`/career/targets/${id}`, data);
}

export function deleteCareerTarget(id) {
  return client.delete(`/career/targets/${id}`);
}

export function listTimelineEvents() {
  return client.get('/career/timeline');
}

export function createTimelineEvent(data) {
  return client.post('/career/timeline', data);
}

export function deleteTimelineEvent(id) {
  return client.delete(`/career/timeline/${id}`);
}

export function reviewResume(file) {
  const formData = new FormData();
  formData.append('file', file);
  return client.post('/career/review-resume', formData, { timeout: 60000 });
}
