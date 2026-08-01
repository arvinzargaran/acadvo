import client from './client';

export function listProjects() {
  return client.get('/projects');
}

export function getProject(id) {
  return client.get(`/projects/${id}`);
}

export function createProject(data) {
  return client.post('/projects', data);
}

export function updateProject(id, data) {
  return client.put(`/projects/${id}`, data);
}

export function deleteProject(id) {
  return client.delete(`/projects/${id}`);
}

export function createMilestone(projectId, data) {
  return client.post(`/projects/${projectId}/milestones`, data);
}

export function updateMilestone(id, data) {
  return client.put(`/projects/milestones/${id}`, data);
}

export function deleteMilestone(id) {
  return client.delete(`/projects/milestones/${id}`);
}
