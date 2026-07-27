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

export function getGPA() {
  return client.get('/degree/gpa');
}

export function listAssessments(courseId) {
  return client.get(`/degree/courses/${courseId}/assessments`);
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
