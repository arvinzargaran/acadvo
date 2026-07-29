import client from './client';

export function getDegreeSummary() {
  return client.get('/degree/summary');
}

export function listRequirements() {
  return client.get('/degree/requirements');
}

export function createRequirement(data) {
  return client.post('/degree/requirements', data);
}

// Credentials UI not yet built — these endpoints exist on the backend but have no frontend implementation
// export function updateRequirement(id, data) {
//   return client.put(`/degree/requirements/${id}`, data);
// }

export function listCourses() {
  return client.get('/degree/courses');
}

export function createCourse(data) {
  return client.post('/degree/courses', data);
}

export function updateCourse(id, data) {
  return client.put(`/degree/courses/${id}`, data);
}

export function deleteCourse(id) {
  return client.delete(`/degree/courses/${id}`);
}

export function listCredentials() {
  return client.get('/degree/credentials');
}

export function createCredential(data) {
  return client.post('/degree/credentials', data);
}

export function updateCredential(id, data) {
  return client.put(`/degree/credentials/${id}`, data);
}

export function deleteCredential(id) {
  return client.delete(`/degree/credentials/${id}`);
}

export function getCatalogStatus() {
  return client.get('/degree/catalog-status');
}

export function getGPA() {
  return client.get('/degree/gpa');
}

export function getGPAGoal(target, remainingCredits) {
  return client.get('/degree/gpa/goal', {
    params: { target, remaining_credits: remainingCredits },
  });
}

export function getGPAGoalMajor(remainingCredits, scope) {
  const params = { remaining_credits: remainingCredits };
  if (scope) params.scope = scope;
  return client.get('/degree/gpa/goal/major', { params });
}

export function listAssessments(courseId) {
  return client.get(`/degree/courses/${courseId}/assessments`);
}

export function createAssessment(courseId, data) {
  return client.post(`/degree/courses/${courseId}/assessments`, data);
}

export function updateAssessment(assessmentId, data) {
  return client.put(`/degree/assessments/${assessmentId}`, data);
}

export function deleteAssessment(assessmentId) {
  return client.delete(`/degree/assessments/${assessmentId}`);
}

export function getGradeProjection(courseId, target) {
  const params = target != null && target !== '' ? { target } : {};
  return client.get(`/degree/courses/${courseId}/grade-projection`, { params });
}

export function parseSyllabus(courseId, file) {
  const formData = new FormData();
  formData.append('file', file);
  return client.post(`/degree/courses/${courseId}/parse-syllabus`, formData, {
    timeout: 60000,
  });
}

export function parseDegreeDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  return client.post('/degree/parse-document', formData, {
    timeout: 60000,
  });
}
