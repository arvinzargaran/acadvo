import api from './client';

export const logStudySession = (data) => {
  return api.post('/study/session', data);
};

export const getStudyStats = () => {
  return api.get('/study/stats');
};
